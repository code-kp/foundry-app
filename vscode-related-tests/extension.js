const childProcess = require("child_process");
const fs = require("fs");
const path = require("path");
const vscode = require("vscode");

const CONTROLLER_ID = "relatedTests";
const CONTROLLER_LABEL = "Related Tests";
const DEFAULT_SOURCE_ROOTS = ["api.py", "server.py", "core", "workspace"];

function activate(context) {
  const workspaceFolder = getWorkspaceFolder();
  if (!workspaceFolder) {
    return;
  }

  const controller = vscode.tests.createTestController(CONTROLLER_ID, CONTROLLER_LABEL);
  const state = {
    controller,
    workspaceFolder,
    metadataScriptPath: path.join(context.extensionPath, "python", "related_tests_metadata.py"),
    scanData: null,
    scanPromise: null,
  };

  controller.resolveHandler = async (item) => {
    if (!item) {
      await refreshController(state);
      return;
    }

    const descriptor = decodeId(item.id);
    if (!descriptor) {
      return;
    }

    if (descriptor.type === "group") {
      await resolveGroup(state, item, descriptor.group);
      return;
    }

    if (descriptor.type === "source") {
      await resolveSource(state, item, descriptor.source);
    }
  };

  controller.createRunProfile(
    "Run",
    vscode.TestRunProfileKind.Run,
    (request, token) => runRelatedTests(state, request, token),
    true,
  );

  context.subscriptions.push(
    controller,
    vscode.commands.registerCommand("relatedTests.refreshController", async () => {
      await vscode.commands.executeCommand("workbench.view.testing");
      await refreshController(state);
    }),
    vscode.commands.registerCommand("relatedTests.refreshItem", async (item) => {
      await refreshSelectedItem(state, item);
    }),
    vscode.workspace.onDidSaveTextDocument((document) => {
      if (document.uri.scheme !== "file") {
        return;
      }
      if (!isInsideWorkspace(document.uri.fsPath, state.workspaceFolder.uri.fsPath)) {
        return;
      }
      invalidateScan(state);
    }),
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration("relatedTests")) {
        invalidateScan(state);
      }
    }),
  );

  showStatusItem(state, "Loading related tests...");
  void refreshController(state);
}

async function refreshController(state) {
  try {
    const scanData = await loadScan(state, true);
    replaceRootItems(state, scanData);
  } catch (error) {
    showStatusItem(state, "Related Tests unavailable", errorMessage(error));
    vscode.window.showErrorMessage(`Related Tests failed to load: ${errorMessage(error)}`);
  }
}

async function refreshSelectedItem(state, item) {
  if (!item) {
    await refreshController(state);
    return;
  }

  const descriptor = decodeId(item.id);
  if (!descriptor) {
    await refreshController(state);
    return;
  }

  if (descriptor.type !== "source") {
    await refreshController(state);
    return;
  }

  try {
    const metadata = await inspectSource(state, descriptor.source);
    if (!hasMetadata(metadata)) {
      removeSourceItem(state, descriptor.source);
      ensureNonEmptyState(state);
      return;
    }

    const sourceItem = getOrCreateSourceItem(state, metadata);
    await resolveSource(state, sourceItem, descriptor.source);
    updateGroupDescription(state, groupForSource(descriptor.source));
  } catch (error) {
    item.error = errorMessage(error);
    vscode.window.showErrorMessage(`Related Tests failed to refresh ${descriptor.source}: ${errorMessage(error)}`);
  }
}

function replaceRootItems(state, scanData) {
  clearCollection(state.controller.items);
  if (!scanData.length) {
    showStatusItem(state, "No related tests found");
    return;
  }

  for (const groupName of groupNames(scanData)) {
    state.controller.items.add(createGroupItem(state, groupName, scanData));
  }
}

async function resolveGroup(state, groupItem, groupName) {
  const scanData = await loadScan(state);
  clearCollection(groupItem.children);

  const groupItems = scanData
    .filter((item) => groupForSource(item.source) === groupName)
    .sort((left, right) => left.source.localeCompare(right.source));

  for (const metadata of groupItems) {
    groupItem.children.add(createSourceItem(state, metadata));
  }

  updateGroupDescription(state, groupName);
}

async function resolveSource(state, sourceItem, sourcePath) {
  const metadata = await inspectSource(state, sourcePath);
  if (!hasMetadata(metadata)) {
    removeSourceItem(state, sourcePath);
    ensureNonEmptyState(state);
    return;
  }

  clearCollection(sourceItem.children);
  applyMetadataState(sourceItem, metadata);

  for (const testPath of metadata.tests) {
    const child = state.controller.createTestItem(
      encodeId({ type: "test", source: metadata.source, test: testPath }),
      testPath.replace(/^tests\//, ""),
      vscode.Uri.file(path.join(state.workspaceFolder.uri.fsPath, testPath)),
    );
    child.description = "pytest";
    sourceItem.children.add(child);
  }
}

async function runRelatedTests(state, request, token) {
  const run = state.controller.createTestRun(request);
  try {
    const plan = await buildExecutionPlan(state, request);
    markStarted(run, plan.groupItems.values());
    markStarted(
      run,
      Array.from(plan.sourceEntries.values())
        .filter((entry) => entry.finalize)
        .map((entry) => entry.item),
    );
    markStarted(run, collectChildItems(plan.testTargets));

    for (const [testPath, target] of plan.testTargets.entries()) {
      if (token.isCancellationRequested) {
        markSkipped(run, remainingTargets(plan.testTargets, testPath));
        break;
      }

      const startedAt = Date.now();
      const outcome = await runPytestFile(state, run, testPath, token);
      const duration = Date.now() - startedAt;
      const message = buildFailureMessage(testPath, outcome.output);

      for (const childItem of target.childItems) {
        childItem.relatedExitCode = outcome.exitCode;
        if (outcome.exitCode === 0) {
          run.passed(childItem, duration);
        } else {
          run.failed(childItem, message, duration);
        }
      }
    }

    finalizeSourceResults(run, plan.sourceEntries);
    finalizeGroupResults(run, plan.groupItems, plan.sourceEntries);
  } catch (error) {
    const rootStatus = currentStatusItem(state);
    if (rootStatus) {
      run.errored(rootStatus, buildFailureMessage("related tests", errorMessage(error)));
    }
    vscode.window.showErrorMessage(`Related Tests failed: ${errorMessage(error)}`);
  } finally {
    run.end();
  }
}

async function buildExecutionPlan(state, request) {
  const scanData = await loadScan(state);
  ensureRootGroups(state, scanData);

  const sourceEntries = new Map();
  const groupItems = new Map();
  const testTargets = new Map();
  const excludedIds = new Set((request.exclude || []).map((item) => item.id));
  const excludedTestIds = new Set();
  for (const item of request.exclude || []) {
    const descriptor = decodeId(item.id);
    if (descriptor && descriptor.type === "test") {
      excludedTestIds.add(descriptor.test);
    }
  }

  const runAll = !request.include || request.include.length === 0;
  const selectedItems = runAll
    ? scanData.map((metadata) => getOrCreateSourceItem(state, metadata))
    : request.include;

  if (runAll) {
    for (const groupName of groupNames(scanData)) {
      groupItems.set(groupName, getOrCreateGroupItem(state, groupName));
    }
  }

  for (const item of selectedItems) {
    const descriptor = decodeId(item.id);
    if (!descriptor || excludedIds.has(item.id)) {
      continue;
    }

    if (descriptor.type === "group") {
      groupItems.set(descriptor.group, getOrCreateGroupItem(state, descriptor.group));
      const groupSources = scanData.filter((metadata) => groupForSource(metadata.source) === descriptor.group);
      for (const metadata of groupSources) {
        const entry = await ensureSourceEntry(state, metadata.source, sourceEntries);
        entry.finalize = true;
        addAllTestsToTargets(entry, testTargets, excludedTestIds);
      }
      continue;
    }

    if (descriptor.type === "source") {
      const entry = await ensureSourceEntry(state, descriptor.source, sourceEntries);
      entry.finalize = true;
      addAllTestsToTargets(entry, testTargets, excludedTestIds);
      groupItems.set(groupForSource(descriptor.source), getOrCreateGroupItem(state, groupForSource(descriptor.source)));
      continue;
    }

    if (descriptor.type === "test") {
      if (excludedTestIds.has(descriptor.test)) {
        continue;
      }
      const entry = await ensureSourceEntry(state, descriptor.source, sourceEntries);
      addTestToTargets(entry, descriptor.test, testTargets);
      groupItems.set(groupForSource(descriptor.source), getOrCreateGroupItem(state, groupForSource(descriptor.source)));
    }
  }

  return { groupItems, sourceEntries, testTargets };
}

async function ensureSourceEntry(state, sourcePath, sourceEntries) {
  if (sourceEntries.has(sourcePath)) {
    return sourceEntries.get(sourcePath);
  }

  const metadata = await inspectSource(state, sourcePath);
  if (!hasMetadata(metadata)) {
    throw new Error(`No related test metadata found for ${sourcePath}.`);
  }

  const sourceItem = getOrCreateSourceItem(state, metadata);
  await resolveSource(state, sourceItem, sourcePath);

  const testItems = new Map();
  sourceItem.children.forEach((child) => {
    const descriptor = decodeId(child.id);
    if (descriptor && descriptor.type === "test") {
      testItems.set(descriptor.test, child);
    }
  });

  const entry = {
    item: sourceItem,
    metadata,
    testItems,
    selectedTests: new Set(),
    finalize: false,
  };
  sourceEntries.set(sourcePath, entry);
  return entry;
}

function addAllTestsToTargets(entry, testTargets, excludedTestIds) {
  for (const [testPath, childItem] of entry.testItems.entries()) {
    if (excludedTestIds.has(testPath)) {
      continue;
    }
    const target = ensureTarget(testTargets, testPath);
    target.childItems.add(childItem);
    entry.selectedTests.add(testPath);
  }
}

function addTestToTargets(entry, testPath, testTargets) {
  const childItem = entry.testItems.get(testPath);
  if (!childItem) {
    return;
  }
  const target = ensureTarget(testTargets, testPath);
  target.childItems.add(childItem);
  entry.selectedTests.add(testPath);
}

function getOrCreateSourceItem(state, metadata) {
  const groupItem = getOrCreateGroupItem(state, groupForSource(metadata.source));
  const sourceId = encodeId({ type: "source", source: metadata.source });
  const existing = groupItem.children.get(sourceId);
  if (existing) {
    applyMetadataState(existing, metadata);
    return existing;
  }

  const item = createSourceItem(state, metadata);
  groupItem.children.add(item);
  updateGroupDescription(state, groupForSource(metadata.source));
  return item;
}

function getOrCreateGroupItem(state, groupName) {
  const id = encodeId({ type: "group", group: groupName });
  const existing = state.controller.items.get(id);
  if (existing) {
    return existing;
  }

  const groupItem = createGroupItem(state, groupName, state.scanData || []);
  state.controller.items.add(groupItem);
  return groupItem;
}

function createGroupItem(state, groupName, scanData) {
  const groupItems = scanData.filter((entry) => groupForSource(entry.source) === groupName);
  const item = state.controller.createTestItem(
    encodeId({ type: "group", group: groupName }),
    groupName === "root" ? "root" : groupName,
  );
  item.canResolveChildren = true;
  item.description = `${groupItems.length} module${groupItems.length === 1 ? "" : "s"}`;
  return item;
}

function createSourceItem(state, metadata) {
  const sourceUri = vscode.Uri.file(path.join(state.workspaceFolder.uri.fsPath, metadata.source));
  const item = state.controller.createTestItem(
    encodeId({ type: "source", source: metadata.source }),
    labelForSource(metadata.source),
    sourceUri,
  );
  item.canResolveChildren = true;
  applyMetadataState(item, metadata);
  return item;
}

function applyMetadataState(item, metadata) {
  item.description = `${metadata.tests.length} related test${metadata.tests.length === 1 ? "" : "s"}`;
  const problems = [];
  for (const error of metadata.errors) {
    problems.push(error);
  }
  for (const missing of metadata.missing_tests) {
    problems.push(`Missing related test file: ${missing}`);
  }
  item.error = problems.length > 0 ? problems.join("\n") : undefined;
}

function removeSourceItem(state, sourcePath) {
  const groupName = groupForSource(sourcePath);
  const groupItem = state.controller.items.get(encodeId({ type: "group", group: groupName }));
  if (!groupItem) {
    return;
  }

  groupItem.children.delete(encodeId({ type: "source", source: sourcePath }));
  updateGroupDescription(state, groupName);
  if (!collectionHasItems(groupItem.children)) {
    state.controller.items.delete(groupItem.id);
  }
}

function updateGroupDescription(state, groupName) {
  const groupItem = state.controller.items.get(encodeId({ type: "group", group: groupName }));
  if (!groupItem) {
    return;
  }

  const count = countCollectionItems(groupItem.children);
  groupItem.description = `${count} module${count === 1 ? "" : "s"}`;
}

function ensureRootGroups(state, scanData) {
  if (hasStatusOnlyRoot(state.controller.items)) {
    replaceRootItems(state, scanData);
    return;
  }

  for (const groupName of groupNames(scanData)) {
    getOrCreateGroupItem(state, groupName);
  }
}

function ensureNonEmptyState(state) {
  if (!collectionHasItems(state.controller.items)) {
    showStatusItem(state, "No related tests found");
  }
}

async function loadScan(state, force = false) {
  if (force) {
    invalidateScan(state);
  }
  if (state.scanData) {
    return state.scanData;
  }
  if (state.scanPromise) {
    return state.scanPromise;
  }

  const args = ["scan", "--workspace", "."];
  for (const sourceRoot of getConfiguration().sourceRoots) {
    args.push("--source-root", sourceRoot);
  }

  state.scanPromise = runPythonJson(state, args)
    .then((result) => {
      state.scanData = Array.isArray(result) ? result : [];
      return state.scanData;
    })
    .finally(() => {
      state.scanPromise = null;
    });

  return state.scanPromise;
}

async function inspectSource(state, sourcePath) {
  const metadata = await runPythonJson(state, ["inspect", "--workspace", ".", sourcePath]);
  if (!state.scanData) {
    state.scanData = [];
  }

  const index = state.scanData.findIndex((item) => item.source === metadata.source);
  if (!hasMetadata(metadata)) {
    if (index >= 0) {
      state.scanData.splice(index, 1);
    }
    return metadata;
  }

  if (index >= 0) {
    state.scanData[index] = metadata;
  } else {
    state.scanData.push(metadata);
    state.scanData.sort((left, right) => left.source.localeCompare(right.source));
  }

  return metadata;
}

function invalidateScan(state) {
  state.scanData = null;
  state.scanPromise = null;
}

function groupNames(scanData) {
  const seen = new Set();
  const groups = [];
  for (const entry of scanData) {
    const groupName = groupForSource(entry.source);
    if (seen.has(groupName)) {
      continue;
    }
    seen.add(groupName);
    groups.push(groupName);
  }
  return groups.sort((left, right) => {
    if (left === "root") {
      return -1;
    }
    if (right === "root") {
      return 1;
    }
    return left.localeCompare(right);
  });
}

function groupForSource(source) {
  return source.includes("/") ? source.split("/", 1)[0] : "root";
}

function labelForSource(source) {
  if (!source.includes("/")) {
    return source;
  }
  const segments = source.split("/");
  return segments.slice(1).join("/");
}

function hasMetadata(metadata) {
  return (metadata.tests && metadata.tests.length > 0) || (metadata.errors && metadata.errors.length > 0);
}

function encodeId(value) {
  return JSON.stringify(value);
}

function decodeId(value) {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function showStatusItem(state, label, errorText) {
  clearCollection(state.controller.items);
  const status = state.controller.createTestItem(
    encodeId({ type: "status", label }),
    label,
  );
  status.error = errorText;
  state.controller.items.add(status);
}

function currentStatusItem(state) {
  let found = null;
  state.controller.items.forEach((item) => {
    const descriptor = decodeId(item.id);
    if (descriptor && descriptor.type === "status") {
      found = item;
    }
  });
  return found;
}

function clearCollection(collection) {
  const ids = [];
  collection.forEach((item) => ids.push(item.id));
  for (const id of ids) {
    collection.delete(id);
  }
}

function collectionHasItems(collection) {
  return countCollectionItems(collection) > 0;
}

function countCollectionItems(collection) {
  let count = 0;
  collection.forEach(() => {
    count += 1;
  });
  return count;
}

function hasStatusOnlyRoot(collection) {
  let count = 0;
  let allStatus = true;
  collection.forEach((item) => {
    count += 1;
    const descriptor = decodeId(item.id);
    if (!descriptor || descriptor.type !== "status") {
      allStatus = false;
    }
  });
  return count === 0 || allStatus;
}

function ensureTarget(targets, testPath) {
  const existing = targets.get(testPath);
  if (existing) {
    return existing;
  }
  const created = { childItems: new Set() };
  targets.set(testPath, created);
  return created;
}

function collectChildItems(testTargets) {
  const items = [];
  for (const target of testTargets.values()) {
    for (const childItem of target.childItems) {
      items.push(childItem);
    }
  }
  return items;
}

function remainingTargets(testTargets, currentTestPath) {
  const remaining = [];
  let foundCurrent = false;
  for (const [testPath, target] of testTargets.entries()) {
    if (!foundCurrent) {
      foundCurrent = testPath === currentTestPath;
      continue;
    }
    for (const childItem of target.childItems) {
      remaining.push(childItem);
    }
  }
  return remaining;
}

function markStarted(run, items) {
  for (const item of items) {
    run.started(item);
  }
}

function markSkipped(run, items) {
  for (const item of items) {
    run.skipped(item);
  }
}

function finalizeSourceResults(run, sourceEntries) {
  for (const entry of sourceEntries.values()) {
    if (!entry.finalize) {
      continue;
    }

    const exitCodes = Array.from(entry.selectedTests)
      .map((testPath) => entry.testItems.get(testPath))
      .filter(Boolean)
      .map((item) => item.relatedExitCode)
      .filter((value) => value !== undefined && value !== null);

    if (exitCodes.length === 0) {
      run.skipped(entry.item);
      continue;
    }

    if (exitCodes.some((code) => code !== 0)) {
      run.failed(entry.item, buildFailureMessage(entry.metadata.source, "One or more related tests failed."));
    } else {
      run.passed(entry.item);
    }
  }
}

function finalizeGroupResults(run, groupItems, sourceEntries) {
  for (const [groupName, groupItem] of groupItems.entries()) {
    const exitCodes = [];
    for (const entry of sourceEntries.values()) {
      if (!entry.finalize || groupForSource(entry.metadata.source) !== groupName) {
        continue;
      }
      for (const testPath of entry.selectedTests) {
        const testItem = entry.testItems.get(testPath);
        if (testItem && testItem.relatedExitCode !== undefined && testItem.relatedExitCode !== null) {
          exitCodes.push(testItem.relatedExitCode);
        }
      }
    }

    if (exitCodes.length === 0) {
      run.skipped(groupItem);
      continue;
    }

    if (exitCodes.some((code) => code !== 0)) {
      run.failed(groupItem, buildFailureMessage(groupName, "One or more related tests failed."));
    } else {
      run.passed(groupItem);
    }
  }
}

async function runPytestFile(state, run, testPath, token) {
  const configuration = getConfiguration();
  const args = ["-m", "pytest", ...configuration.pytestArgs, testPath];
  const workspaceRoot = state.workspaceFolder.uri.fsPath;

  return new Promise((resolve, reject) => {
    const process = childProcess.spawn(configuration.pythonCommand, args, {
      cwd: workspaceRoot,
      env: processEnv(),
    });

    let output = "";
    let settled = false;

    const finish = (value, isError = false) => {
      if (settled) {
        return;
      }
      settled = true;
      if (isError) {
        reject(value);
      } else {
        resolve(value);
      }
    };

    process.stdout.on("data", (chunk) => {
      const text = chunk.toString();
      output += text;
      run.appendOutput(text);
    });

    process.stderr.on("data", (chunk) => {
      const text = chunk.toString();
      output += text;
      run.appendOutput(text);
    });

    process.on("error", (error) => {
      finish(new Error(`Failed to start pytest for ${testPath}: ${error.message}`), true);
    });

    process.on("close", (exitCode) => {
      finish({ exitCode: exitCode === null ? 1 : exitCode, output });
    });

    token.onCancellationRequested(() => {
      process.kill();
    });
  });
}

function buildFailureMessage(label, output) {
  const trimmed = output.trim();
  const text = trimmed ? trimmed.slice(0, 12000) : `${label} failed.`;
  return new vscode.TestMessage(text);
}

function getConfiguration() {
  const config = vscode.workspace.getConfiguration("relatedTests");
  const sourceRoots = config.get("sourceRoots", DEFAULT_SOURCE_ROOTS);
  return {
    pythonCommand: resolvePythonCommand(config),
    pytestArgs: config.get("pytestArgs", []),
    sourceRoots: Array.isArray(sourceRoots) && sourceRoots.length > 0 ? sourceRoots : DEFAULT_SOURCE_ROOTS,
  };
}

function resolvePythonCommand(config) {
  const configured = config.get("pythonCommand", "");
  if (typeof configured === "string" && configured.trim()) {
    return configured.trim();
  }

  const pythonConfig = vscode.workspace.getConfiguration("python");
  const interpreterPath = pythonConfig.get("defaultInterpreterPath", "");
  if (typeof interpreterPath === "string" && interpreterPath.trim()) {
    return interpreterPath.trim();
  }

  const workspaceFolder = getWorkspaceFolder();
  if (workspaceFolder) {
    const venvPython = process.platform === "win32"
      ? path.join(workspaceFolder.uri.fsPath, ".venv", "Scripts", "python.exe")
      : path.join(workspaceFolder.uri.fsPath, ".venv", "bin", "python");
    if (fs.existsSync(venvPython)) {
      return venvPython;
    }
  }

  return "python3";
}

function runPythonJson(state, args) {
  const configuration = getConfiguration();
  const workspaceRoot = state.workspaceFolder.uri.fsPath;

  return new Promise((resolve, reject) => {
    const process = childProcess.spawn(
      configuration.pythonCommand,
      [state.metadataScriptPath, ...args],
      {
        cwd: workspaceRoot,
        env: processEnv(),
      },
    );

    let stdout = "";
    let stderr = "";

    process.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });

    process.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    process.on("error", (error) => {
      reject(new Error(`Failed to start metadata inspection: ${error.message}`));
    });

    process.on("close", (exitCode) => {
      if (exitCode !== 0) {
        reject(new Error(stderr.trim() || stdout.trim() || `Metadata inspection exited with code ${exitCode}.`));
        return;
      }

      try {
        resolve(JSON.parse(stdout || "null"));
      } catch (error) {
        reject(new Error(`Metadata inspection did not return valid JSON: ${error.message}`));
      }
    });
  });
}

function processEnv() {
  return { ...process.env };
}

function isInsideWorkspace(filePath, workspaceRoot) {
  const relative = path.relative(workspaceRoot, filePath);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

function getWorkspaceFolder() {
  const folders = vscode.workspace.workspaceFolders || [];
  return folders[0] || null;
}

function errorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}

function deactivate() {}

module.exports = {
  activate,
  deactivate,
};
