// // --- Main Process ---
// const { app, BrowserWindow } = require("electron");
// const path = require("path");
// const { spawn } = require("child_process");

// let pyProc = null;

// function createPyProc() {
//   // choose exe name (if you ever support other OSes)
//   const exeName = process.platform === "win32" ? "run.exe" : "run";

//   // When packaged, extraResources copies files to process.resourcesPath
//   // In dev (not packaged) the exe is relative to the project; adjust accordingly.
//   const exePath = app.isPackaged
//     ? path.join(process.resourcesPath, "build", exeName)
//     : path.join(__dirname, "..", "build", exeName);

//   console.log("Attempting to spawn backend exe at:", exePath);

//   try {
//     pyProc = spawn(exePath, [], {
//       windowsHide: true,
//       // detached: false is fine; set to true if you want child to live after app quits
//       stdio: ["ignore", "pipe", "pipe"],
//     });
//   } catch (err) {
//     console.error("spawn threw an exception:", err);
//     pyProc = null;
//   }

//   if (!pyProc) {
//     throw new Error("Flask backend failed to start (spawn returned null)!");
//   }

//   // helpful logging — capture stdout/stderr so you will see runtime errors in logs
//   pyProc.stdout &&
//     pyProc.stdout.on("data", (d) => console.log("[py stdout]", d.toString()));
//   pyProc.stderr &&
//     pyProc.stderr.on("data", (d) => console.error("[py stderr]", d.toString()));

//   pyProc.on("error", (err) => {
//     console.error("pyProc spawn error:", err);
//   });

//   pyProc.on("exit", (code, signal) => {
//     console.log(`pyProc exited. code=${code} signal=${signal}`);
//     pyProc = null;
//   });

//   console.log("Flask server spawn attempted.");
// }

// // // Lunch the flask app when Electron starts
// // function createPyProc() {
// //   const script = path.join(__dirname, "../build/run.exe");
// //   pyProc = spawn(script);

// //   if (!pyProc) throw new Error("Flask backend failed to start!");
// //   console.log("Flask server started successfully!");
// // }

// function createWindow() {
//   mainWindow = new BrowserWindow({
//     width: 1200,
//     height: 800,
//     webPreferences: {
//       preload: path.join(__dirname, "preload.js"),
//     },
//   });

//   // Wait for Flask to start before laoding
//   setTimeout(() => {
//     mainWindow.loadURL("http://127.0.0.1:5000/");
//   }, 4000); //will check the wait time later and adjust as needed

//   mainWindow.on("closed", () => {
//     mainWindow = null;
//     if (pyProc) pyProc.kill();
//   });
// }

// app.whenReady().then(() => {
//   createPyProc();
//   createWindow();

//   app.on("activate", () => {
//     if (BrowserWindow.getAllWindows().length === 0) createWindow();
//   });
// });

// app.on("window-all-closed", () => {
//   if (process.platform !== "darwin") {
//     app.quit();
//   }
// });

// --- NEW DEV ---

// electron/main.js
// Launches the bundled Flask backend executable, waits for it to become healthy,
// then opens a BrowserWindow pointed to the local server.

// electron/main.js
// Electron main process: start/stop the bundled Flask backend executable,
// wait for it to be ready, then load the app UI from the local server.
//
// Behavior:
// - Development: uses the EXE at ../dist/edusync_backend(.exe)
// - Packaged: uses the EXE copied to resources/backend/edusync_backend(.exe)
//   (ensure you used extraResources in package.json to copy ../dist -> backend)

// --- OLD WORKING FILE ---
// const { app, BrowserWindow, dialog } = require("electron");
// const path = require("path");
// const fs = require("fs");
// const { spawn } = require("child_process");
// const http = require("http");

// let backendProcess = null;
// let mainWindow = null;

// // Return the expected backend executable filename for the current platform
// function getBackendExeName() {
//   return process.platform === "win32"
//     ? "edusync_backend.exe"
//     : "edusync_backend";
// }

// function backendExePath() {
//   const exeName = getBackendExeName();

//   if (app.isPackaged) {
//     // Installed app: resources path is root for assets placed by electron-builder
//     // extraResources: { from: "../dist", to: "backend" } -> resources/backend/<exe>
//     return path.join(process.resourcesPath, "backend", exeName);
//   } else {
//     // Development: look at ../dist relative to electron folder
//     // i.e., EduSync/electron -> back to EduSync/dist
//     return path.join(__dirname, "..", "dist", exeName);
//   }
// }

// function startBackend() {
//   const exe = backendExePath();

//   if (!fs.existsSync(exe)) {
//     const msg = `Backend executable not found at: ${exe}`;
//     console.error(msg);

//     // Show user-facing dialog when packaged; in dev we log only.
//     if (app.isPackaged) {
//       dialog.showErrorBox(
//         "Missing backend",
//         msg + "\nPlease reinstall or contact support."
//       );
//     }

//     return Promise.reject(new Error(msg));
//   }

//   try {
//     backendProcess = spawn(exe, [], {
//       cwd: path.dirname(exe),
//       windowsHide: true,
//       detached: false, // keep child attached so it dies with the main process
//     });
//   } catch (spawnErr) {
//     console.error("Failed to spawn backend:", spawnErr);
//     return Promise.reject(spawnErr);
//   }

//   // Handle spawn errors (e.g., permission issues or ENOENT surfaced later)
//   backendProcess.on("error", (err) => {
//     console.error("Backend process error:", err);
//     // Optionally show a dialog to the user if packaged
//     if (app.isPackaged) {
//       dialog.showErrorBox("Backend failed to start", String(err));
//     }
//   });

//   // Forward stdout/stderr to the Electron console for easier debugging
//   backendProcess.stdout?.on("data", (d) => {
//     console.log("[backend stdout]", d.toString());
//   });
//   backendProcess.stderr?.on("data", (d) => {
//     console.error("[backend stderr]", d.toString());
//   });

//   backendProcess.on("exit", (code, signal) => {
//     console.log("Backend process exited", code, signal);
//     backendProcess = null;
//   });

//   console.log("Spawned backend from", exe);
//   return Promise.resolve();
// }

// /**
//  * Stop the backend process if running.
//  */
// function stopBackend() {
//   if (backendProcess && !backendProcess.killed) {
//     try {
//       backendProcess.kill();
//       backendProcess = null;
//     } catch (e) {
//       console.warn("Failed to kill backend process", e);
//     }
//   }
// }

// /**
//  * Poll the given URL until it returns HTTP 200 or the timeout elapses.
//  * Used to wait for the Flask backend to be ready before loading the UI.
//  */
// function waitForBackendReady(url, timeout = 15000) {
//   const start = Date.now();
//   return new Promise((resolve, reject) => {
//     (function poll() {
//       http
//         .get(url, (res) => {
//           if (res.statusCode === 200) {
//             resolve();
//           } else {
//             if (Date.now() - start > timeout) {
//               reject(new Error("Timeout waiting for backend"));
//             } else {
//               setTimeout(poll, 300);
//             }
//           }
//         })
//         .on("error", () => {
//           if (Date.now() - start > timeout) {
//             reject(new Error("Timeout waiting for backend"));
//           } else {
//             setTimeout(poll, 300);
//           }
//         });
//     })();
//   });
// }

// /**
//  * Create the main BrowserWindow. Start the backend (unless an explicit
//  * ELECTRON_START_URL is provided for dev), wait for health-check, then load UI.
//  */
// async function createWindow() {
//   mainWindow = new BrowserWindow({
//     width: 1100,
//     height: 700,
//     webPreferences: {
//       nodeIntegration: false,
//       contextIsolation: true,
//       preload: path.join(__dirname, "preload.js"),
//     },
//   });

//   // Default server URL used by the Flask backend
//   const serverUrl = "http://127.0.0.1:5000";

//   // If ELECTRON_START_URL is set (dev workflow), skip starting the bundled exe
//   if (process.env.ELECTRON_START_URL === undefined) {
//     try {
//       await startBackend();
//     } catch (err) {
//       // startBackend failure is fatal for the packaged app; log and show dialog
//       console.error("Failed to start backend:", err);
//       // If packaged, show a dialog and quit; in dev we continue so you can debug
//       if (app.isPackaged) {
//         dialog.showErrorBox(
//           "App error",
//           "Failed to start backend.\n" + String(err)
//         );
//         app.quit();
//         return;
//       }
//     }

//     try {
//       await waitForBackendReady(serverUrl + "/api/ping", 20000);
//     } catch (err) {
//       console.error("Backend did not start in time", err);
//       // In packaged app, inform user and close. In dev, continue to load UI (maybe backend started later).
//       if (app.isPackaged) {
//         dialog.showErrorBox(
//           "Backend startup timeout",
//           "The backend did not respond in time. Please try again or reinstall."
//         );
//         stopBackend();
//         app.quit();
//         return;
//       }
//     }
//   } else {
//     // In dev with ELECTRON_START_URL set, we let the developer control the backend
//     console.log("ELECTRON_START_URL detected; skipping bundled backend spawn");
//   }

//   // Load the UI from the running Flask server (or from ELECTRON_START_URL if set externally)
//   const loadUrl = process.env.ELECTRON_START_URL || serverUrl;
//   try {
//     await mainWindow.loadURL(loadUrl);
//   } catch (loadErr) {
//     console.error("Failed to load URL", loadUrl, loadErr);
//     if (app.isPackaged) {
//       dialog.showErrorBox(
//         "Load error",
//         "Failed to load the app UI: " + String(loadErr)
//       );
//     }
//   }

//   mainWindow.on("closed", () => {
//     mainWindow = null;
//   });
// }

// // App lifecycle
// app.whenReady().then(createWindow);

// app.on("window-all-closed", () => {
//   // On macOS, apps usually stay open until explicit quit
//   if (process.platform !== "darwin") {
//     stopBackend();
//     app.quit();
//   }
// });

// app.on("before-quit", () => {
//   // Ensure backend is stopped before the app quits
//   stopBackend();
// });

// app.on("activate", () => {
//   if (BrowserWindow.getAllWindows().length === 0) createWindow();
// });
// --- ENDS HERE ---

// main.js (hardened version)

const { app, BrowserWindow, dialog } = require("electron");
const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");
const http = require("http");

let backendProcess = null;
let mainWindow = null;
let shuttingDown = false;

/**
 * Return the expected backend executable filename for the current platform.
 */
function getBackendExeName() {
  return process.platform === "win32"
    ? "edusync_backend.exe"
    : "edusync_backend";
}

/**
 * Resolve the absolute path to the backend executable.
 *
 * Dev assumption:
 *   project/
 *     electron/main.js  (this file)
 *     dist/edusync_backend(.exe)
 *
 * Packaged assumption (electron-builder style):
 *   <install dir>/
 *     resources/
 *       backend/edusync_backend(.exe)
 */
function backendExePath() {
  const exeName = getBackendExeName();

  if (app.isPackaged) {
    return path.join(process.resourcesPath, "backend", exeName);
  } else {
    return path.join(__dirname, "..", "dist", exeName);
  }
}

/**
 * Spawn the backend if not already running.
 * On POSIX we spawn detached so we get a separate process group we can kill by pgid later.
 * On Windows we keep it attached and later nuke the tree with taskkill.
 */
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

app.whenReady().then(createWindow);

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
