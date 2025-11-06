// electron/preload.js
// Optional: expose safe APIs to renderer if needed.
const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("edusync", {
  // add safe helpers if you need to call native features
});
