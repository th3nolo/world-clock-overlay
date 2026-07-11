const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  setIgnoreMouseEvents: (ignore, options) => ipcRenderer.send('set-ignore-mouse-events', ignore, options),
  toggleAlwaysOnTop: () => ipcRenderer.send('toggle-always-on-top'),
  closeApp: () => ipcRenderer.send('close-app'),
  minimizeApp: () => ipcRenderer.send('minimize-app'),
  resizeWindow: (width, height) => ipcRenderer.send('resize-window', width, height),
  onAlwaysOnTopStatus: (callback) => {
    const subscription = (event, status) => callback(status);
    ipcRenderer.on('always-on-top-status', subscription);
    return () => ipcRenderer.removeListener('always-on-top-status', subscription);
  },
  isElectron: true
});
