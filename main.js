const { app, BrowserWindow, ipcMain, screen } = require('electron');
const path = require('path');
const fs = require('fs');

// Path to store window settings (position, size)
const settingsPath = path.join(app.getPath('userData'), 'window-settings.json');

let mainWindow;

function loadSettings() {
  try {
    if (fs.existsSync(settingsPath)) {
      return JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
    }
  } catch (e) {
    console.error('Failed to load settings', e);
  }
  return { width: 420, height: 160, x: null, y: null };
}

function saveSettings(settings) {
  try {
    fs.writeFileSync(settingsPath, JSON.stringify(settings), 'utf8');
  } catch (e) {
    console.error('Failed to save settings', e);
  }
}

function createWindow() {
  // Load saved position or calculate default (bottom right)
  const savedSettings = loadSettings();
  
  // Set up transparent visuals for Linux compatibility
  if (process.platform === 'linux') {
    app.commandLine.appendSwitch('enable-transparent-visuals');
  }

  mainWindow = new BrowserWindow({
    width: savedSettings.width || 420,
    height: savedSettings.height || 160,
    x: savedSettings.x,
    y: savedSettings.y,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: true,
    maximizable: false,
    fullscreenable: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
    // Make sure it doesn't show up in Alt+Tab as a standard blocky window if not wanted,
    // though keeping it in taskbar is generally good for closing it.
    skipTaskbar: false,
  });

  // If no position saved, place it in the bottom-right corner of the primary display
  if (savedSettings.x === null || savedSettings.y === null) {
    const primaryDisplay = screen.getPrimaryDisplay();
    const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize;
    const x = screenWidth - (savedSettings.width || 420) - 20;
    const y = screenHeight - (savedSettings.height || 160) - 40;
    mainWindow.setPosition(x, y);
  }

  mainWindow.loadFile('index.html');

  // Stays always on top even over full screen windows (on macOS/Windows)
  mainWindow.setAlwaysOnTop(true, 'screen-saver');

  // Monitor window movement/resize to save bounds
  const saveBounds = () => {
    if (!mainWindow) return;
    const bounds = mainWindow.getBounds();
    saveSettings({
      width: bounds.width,
      height: bounds.height,
      x: bounds.x,
      y: bounds.y
    });
  };

  mainWindow.on('moved', saveBounds);
  mainWindow.on('resized', saveBounds);

  mainWindow.on('closed', function () {
    mainWindow = null;
  });
}

// IPC Handlers
ipcMain.on('set-ignore-mouse-events', (event, ignore, options) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (win) {
    // ignore: true means click events pass through the window
    // forward: true means mousemove events are still fired in the renderer
    win.setIgnoreMouseEvents(ignore, options || { forward: true });
  }
});

ipcMain.on('toggle-always-on-top', (event) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (win) {
    const isTop = win.isAlwaysOnTop();
    win.setAlwaysOnTop(!isTop, 'screen-saver');
    event.reply('always-on-top-status', !isTop);
  }
});

ipcMain.on('close-app', () => {
  app.quit();
});

ipcMain.on('minimize-app', () => {
  if (mainWindow) mainWindow.minimize();
});

ipcMain.on('resize-window', (event, width, height) => {
  if (mainWindow) {
    mainWindow.setSize(Math.round(width), Math.round(height));
  }
});

app.whenReady().then(() => {
  createWindow();

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') app.quit();
});
