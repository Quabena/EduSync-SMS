const { app, BrowserWindow, dialog } = require("electron");
const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");
const http = require("http");

let backendProcess = null;
let mainWindow = null;
let shuttingDown = false;

// Helper for dotenv integration:
function ensureEnvFile() {
  const userData = app.getPath("appData");
  const envDir = path.join(userData, "EduSync SMS");
  const envPath = path.join(envDir, ".env");

  if (!fs.existsSync(envDir)) {
    fs.mkdirSync(envDir, { recursive: true });
  }

  if (!fs.existsSync(envPath)) {
    // Generate secure values
    const crypto = require("crypto");
    const secretKey = crypto.randomBytes(32).toString("hex");
    const machineId = crypto.randomBytes(16).toString("hex");

    const envContent =
      `SECRET_KEY=${secretKey}\n` +
      `MACHINE_ID=${machineId}\n` +
      `DEBUG=False\n`;

    fs.writeFileSync(envPath, envContent, "utf8");
    console.log("Generated new .env at", envPath);
  }

  return envPath;
}

/**
 * Return the expected backend executable filename for the current platform.
 */
function getBackendExeName() {
  return process.platform === "win32" ? "EduSync.exe" : "EduSync";
}

function backendExePath() {
  const exeName = getBackendExeName();

  if (app.isPackaged) {
    return path.join(process.resourcesPath, "backend", exeName);
  } else {
    return path.join(__dirname, "..", "dist", exeName);
  }
}

function startBackend() {
  if (backendProcess) return backendProcess;

  const exe = backendExePath();

  if (!fs.existsSync(exe)) {
    const msg = `Backend executable not found at: ${exe}`;
    console.error(msg);

    if (app.isPackaged) {
      dialog.showErrorBox(
        "Missing backend",
        msg + "\nPlease reinstall or contact support."
      );
    }

    throw new Error(msg);
  }

  // On Windows we keep detached: false.
  // On POSIX we prefer detached: true so we can kill process group (-pid).
  const shouldDetach = process.platform !== "win32";

  try {
    backendProcess = spawn(exe, [], {
      cwd: path.dirname(exe),
      windowsHide: true,
      detached: shouldDetach,
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (spawnErr) {
    console.error("Failed to spawn backend:", spawnErr);
    throw spawnErr;
  }

  // Log backend output for debugging/support.
  backendProcess.stdout?.on("data", (d) => {
    console.log("[backend stdout]", d.toString());
  });
  backendProcess.stderr?.on("data", (d) => {
    console.error("[backend stderr]", d.toString());
  });

  backendProcess.on("error", (err) => {
    console.error("Backend process error:", err);
    if (app.isPackaged) {
      dialog.showErrorBox("Backend failed to start", String(err));
    }
  });

  backendProcess.on("exit", (code, signal) => {
    console.log("Backend process exited", { code, signal });
    backendProcess = null;
  });

  console.log(
    `Spawned backend from ${exe} pid=${backendProcess.pid} detached=${shouldDetach}`
  );

  return backendProcess;
}

/**
 * Wait up to `ms` milliseconds for a process to exit.
 */
function waitForExit(proc, ms) {
  return new Promise((resolve) => {
    let done = false;
    const timer = setTimeout(() => {
      if (!done) resolve();
    }, ms);

    proc.once("exit", () => {
      done = true;
      clearTimeout(timer);
      resolve();
    });
  });
}

/**
 * Stop the backend process if running.
 * This tries graceful first (SIGTERM / kill), then forces kill of entire tree.
 * It's async so it can be awaited during shutdown.
 */
async function stopBackend(graceMs = 1500) {
  if (!backendProcess) return;

  const proc = backendProcess;
  backendProcess = null; // prevent double kill races

  console.log("Stopping backend pid=", proc.pid);

  try {
    if (process.platform === "win32") {
      // Ask nicely
      try {
        proc.kill(); // sends a TERM-like signal on Windows
      } catch (e) {
        console.warn("proc.kill() (TERM) on win32 failed:", e);
      }

      // Give it a moment
      await waitForExit(proc, graceMs);

      // Still not dead? Use taskkill /T /F to kill the process and all children.
      if (!proc.killed) {
        console.warn("Backend still alive; forcing taskkill tree:", proc.pid);
        try {
          spawn("taskkill", ["/PID", String(proc.pid), "/T", "/F"], {
            windowsHide: true,
            stdio: "ignore",
          });
        } catch (taskkillErr) {
          console.error("taskkill failed:", taskkillErr);
        }
      }
    } else {
      // POSIX: kill the process group (-pid) so we catch worker children too.
      try {
        process.kill(-proc.pid, "SIGTERM");
      } catch (groupErr) {
        console.warn(
          "Group SIGTERM failed, fallback to direct SIGTERM:",
          groupErr
        );
        try {
          proc.kill("SIGTERM");
        } catch (directErr) {
          console.warn("Direct SIGTERM failed:", directErr);
        }
      }

      // Wait a bit
      await waitForExit(proc, graceMs);

      // Still around? SIGKILL the whole group.
      if (!proc.killed) {
        console.warn("Backend still alive; forcing SIGKILL group:", proc.pid);
        try {
          process.kill(-proc.pid, "SIGKILL");
        } catch (killGroupErr) {
          console.warn(
            "Group SIGKILL failed, fallback to direct SIGKILL:",
            killGroupErr
          );
          try {
            proc.kill("SIGKILL");
          } catch (killErr) {
            console.error("Direct SIGKILL failed:", killErr);
          }
        }
      }
    }
  } catch (err) {
    console.warn("Failed to stop backend cleanly:", err);
  }
}

/**
 * Poll the given URL until it returns HTTP 200 or the timeout elapses.
 * Used to wait for the backend to be ready before loading the UI.
 */
function waitForBackendReady(url, timeout = 15000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    (function poll() {
      http
        .get(url, (res) => {
          if (res.statusCode === 200) {
            resolve();
          } else {
            if (Date.now() - start > timeout) {
              reject(new Error("Timeout waiting for backend"));
            } else {
              setTimeout(poll, 300);
            }
          }
        })
        .on("error", () => {
          if (Date.now() - start > timeout) {
            reject(new Error("Timeout waiting for backend"));
          } else {
            setTimeout(poll, 300);
          }
        });
    })();
  });
}

/**
 * Create the main BrowserWindow. Start the backend (unless ELECTRON_START_URL
 * is provided for dev), wait for /api/ping, then load UI.
 */
async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 700,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });

  // Default URL served by your backend API (Flask/FastAPI/etc.)
  const serverUrl = "http://127.0.0.1:5000";

  // In dev, you can point ELECTRON_START_URL to a dev server (e.g. Vite/React),
  // and in that case we do NOT spawn the bundled backend.
  const devOverrideUrl = process.env.ELECTRON_START_URL;
  const shouldSpawnBackend = devOverrideUrl === undefined;

  if (shouldSpawnBackend) {
    // 1. start backend
    try {
      startBackend();
    } catch (err) {
      console.error("Failed to start backend:", err);

      if (app.isPackaged) {
        dialog.showErrorBox(
          "App error",
          "Failed to start backend.\n" + String(err)
        );
        await stopBackend();
        await gracefulAppQuit(1);
        return;
      }
    }

    // 2. wait for backend health
    try {
      await waitForBackendReady(serverUrl + "/api/ping", 20000);
    } catch (err) {
      console.error("Backend did not start in time:", err);

      if (app.isPackaged) {
        dialog.showErrorBox(
          "Backend startup timeout",
          "The backend did not respond in time. Please try again or reinstall."
        );
        await stopBackend();
        await gracefulAppQuit(1);
        return;
      }
    }
  } else {
    console.log(
      "ELECTRON_START_URL detected; skipping bundled backend spawn (dev mode)"
    );
  }

  // 3. load UI (either the backend URL or the dev override)
  const loadUrl = devOverrideUrl || serverUrl;
  try {
    await mainWindow.loadURL(loadUrl);
  } catch (loadErr) {
    console.error("Failed to load URL", loadUrl, loadErr);
    if (app.isPackaged) {
      dialog.showErrorBox(
        "Load error",
        "Failed to load the app UI: " + String(loadErr)
      );
    }
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

/**
 * Central shutdown sequence. We call this from ALL exit paths.
 * - Ensures we only run shutdown once.
 * - Stops backend.
 * - Exits Electron.
 */
async function gracefulAppQuit(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;

  await stopBackend();

  // app.exit() is a hard exit without re-triggering Electron lifecycle.
  app.exit(code);
}

// ----------------- App lifecycle -----------------

app.whenReady().then(async () => {
  ensureEnvFile(); // <— ADD THIS LINE
  await createWindow();
});

// IMPORTANT CHANGE vs your original:
// We now quit the whole app (and kill the backend) when all windows close,
// EVEN on macOS. This prevents "invisible app but backend still running."
app.on("window-all-closed", async () => {
  await gracefulAppQuit(0);
});

// before-quit can fire multiple times;
// we intercept the first one so we can async cleanup first.
app.on("before-quit", async (e) => {
  if (!shuttingDown) {
    e.preventDefault();
    await gracefulAppQuit(0);
  }
});

app.on("activate", () => {
  // Typical macOS behavior: recreate a window if user clicks dock icon
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

// ----------------- Process-level safety nets -----------------

// If the user hits Ctrl+C in dev, or system sends SIGTERM, etc.
process.on("SIGINT", () => {
  gracefulAppQuit(0);
});
process.on("SIGTERM", () => {
  gracefulAppQuit(0);
});

// If something blows up in the main process, still clean the backend.
process.on("uncaughtException", (err) => {
  console.error("Uncaught exception in main process:", err);
  gracefulAppQuit(1);
});

// Final fallback: Node process is exiting. We can't await here,
// but stopBackend() is idempotent so it's safe to call.
process.on("exit", () => {
  // best effort cleanup
  if (backendProcess) {
    // fire-and-forget; don't await
    stopBackend();
  }
});
