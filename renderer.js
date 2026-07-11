// Timezones defined
const TIMEZONES = {
  venezuela: 'America/Caracas',
  ksa: 'Asia/Riyadh',
  spain: 'Europe/Madrid'
};

// Check if running inside Electron
const isElectron = window.electronAPI && window.electronAPI.isElectron;

// State management
let state = {
  format: '12h',        // '12h' or '24h'
  showSeconds: true,
  layout: 'horizontal',  // 'horizontal' or 'vertical'
  opacity: 65,          // 15 to 100
  scale: 100,           // 70 to 150
  theme: 'glass-dark',  // 'glass-dark', 'glass-light', 'cyberpunk', 'nordic'
  clickThrough: false,
  settingsOpen: false
};

// Load settings from localStorage
function loadState() {
  const savedState = localStorage.getItem('world-clock-state');
  if (savedState) {
    try {
      state = { ...state, ...JSON.parse(savedState) };
    } catch (e) {
      console.error('Error loading saved state', e);
    }
  }
  
  // Sync state with UI controls
  document.getElementById('select-format').value = state.format;
  document.getElementById('toggle-seconds').checked = state.showSeconds;
  document.getElementById('select-layout').value = state.layout;
  document.getElementById('slider-opacity').value = state.opacity;
  document.getElementById('slider-scale').value = state.scale;
  document.getElementById('toggle-click-through').checked = state.clickThrough;
  
  document.getElementById('val-opacity').textContent = `${state.opacity}%`;
  document.getElementById('val-scale').textContent = `${(state.scale / 100).toFixed(1)}x`;
  
  // Highlight active theme button
  document.querySelectorAll('.theme-btn').forEach(btn => {
    if (btn.dataset.theme === state.theme) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  applyState();
}

// Save settings to localStorage
function saveState() {
  localStorage.setItem('world-clock-state', JSON.stringify(state));
}

// Apply settings to elements
function applyState() {
  const widget = document.getElementById('clock-widget');
  
  // 1. Layout Orientation
  widget.className = `${state.layout} interactive ${state.theme}`;
  
  // 2. Opacity
  widget.style.setProperty('--glass-opacity', state.opacity / 100);
  
  // 3. Scaling
  widget.style.setProperty('--size-scale', state.scale / 100);
  
  // 4. Electron body class setup
  if (isElectron) {
    document.body.classList.add('is-electron');
  }

  // Adjust window size for Electron process
  fitWindow();
}

// Fit Electron window to HTML widget bounds dynamically
function fitWindow() {
  if (!isElectron) return;
  
  // Wait for rendering to complete
  setTimeout(() => {
    const container = document.getElementById('widget-container');
    const rect = container.getBoundingClientRect();
    
    // Scale factor
    const scale = state.scale / 100;
    
    // Add extra padding for shadows/boundaries
    const padding = 15; 
    const width = (rect.width * scale) + padding;
    const height = (rect.height * scale) + padding;
    
    window.electronAPI.resizeWindow(width, height);
  }, 50);
}

// Compute timezone offsets relative to the user's local timezone
function getOffsetDiff(timeZone) {
  try {
    const now = new Date();
    
    // Get target date components
    const targetString = now.toLocaleString('en-US', { timeZone, timeZoneName: 'longOffset' });
    const match = targetString.match(/GMT([+-]\d+)(?::(\d+))?/);
    if (!match) return '';
    
    const targetHours = parseInt(match[1], 10);
    const targetMinutes = match[2] ? parseInt(match[2], 10) : 0;
    const targetOffsetMinutes = (targetHours * 60) + (targetHours >= 0 ? targetMinutes : -targetMinutes);
    
    // Local timezone offset in minutes (JS returns opposite sign)
    const localOffsetMinutes = -now.getTimezoneOffset();
    
    const diffMinutes = targetOffsetMinutes - localOffsetMinutes;
    const diffHours = diffMinutes / 60;
    
    if (diffHours === 0) return 'Local';
    const sign = diffHours > 0 ? '+' : '';
    const diffStr = Number.isInteger(diffHours) ? diffHours.toString() : diffHours.toFixed(1);
    return `${sign}${diffStr}h`;
  } catch (e) {
    console.error('Offset calculation failed', e);
    return '';
  }
}

// Tick update: update times, dates, and offsets
function tick() {
  const now = new Date();
  const use24h = state.format === '24h';
  
  for (const [id, timezone] of Object.entries(TIMEZONES)) {
    // 1. Time string formatting
    const timeOptions = {
      timeZone: timezone,
      hour: '2-digit',
      minute: '2-digit',
      hour12: !use24h
    };
    if (state.showSeconds) {
      timeOptions.second = '2-digit';
    }
    
    try {
      const timeFormatter = new Intl.DateTimeFormat('en-US', timeOptions);
      const parts = timeFormatter.formatToParts(now);
      
      let timeStr = '';
      let periodStr = '';
      
      parts.forEach(part => {
        if (part.type === 'dayPeriod') {
          periodStr = part.value;
        } else if (part.type !== 'literal' || part.value === ':') {
          timeStr += part.value;
        }
      });
      
      const timeEl = document.getElementById(`time-${id}`);
      const periodEl = document.getElementById(`period-${id}`);
      
      if (timeEl) timeEl.textContent = timeStr.trim();
      if (periodEl) {
        periodEl.textContent = periodStr;
        periodEl.style.display = periodStr ? 'inline' : 'none';
      }
      
      // 2. Date formatting
      const dateOptions = {
        timeZone: timezone,
        weekday: 'short',
        month: 'short',
        day: 'numeric'
      };
      const dateFormatter = new Intl.DateTimeFormat('en-US', dateOptions);
      const dateEl = document.getElementById(`date-${id}`);
      if (dateEl) {
        dateEl.textContent = dateFormatter.format(now);
      }
      
      // 3. Offset update
      const offsetEl = document.getElementById(`offset-${id}`);
      if (offsetEl) {
        offsetEl.textContent = getOffsetDiff(timezone);
      }
    } catch (e) {
      console.error(`Error updating clock for ${id}:`, e);
    }
  }
}

// Click-through / Mouse Transparency Handler (Electron only)
// Makes the transparent areas of the widget click-through while keeping cards/controls clickable.
function initClickThrough() {
  if (!isElectron) return;
  
  window.addEventListener('mousemove', (e) => {
    if (!state.clickThrough) {
      // Normal mode: window is solid to the mouse
      window.electronAPI.setIgnoreMouseEvents(false);
      return;
    }
    
    // Click-through mode is active.
    // Check if the mouse is hovering over any element marked as '.interactive'
    // or inside an '.interactive' block.
    const isInteractive = e.target.closest('.interactive') !== null;
    
    if (isInteractive) {
      // Mouse is over an interactive button/card: enable clicking it
      window.electronAPI.setIgnoreMouseEvents(false);
    } else {
      // Mouse is over empty transparent space: ignore clicks (click-through to desktop)
      window.electronAPI.setIgnoreMouseEvents(true, { forward: true });
    }
  });

  // Double-click on background (non-interactive area) to toggle click-through mode
  window.addEventListener('dblclick', (e) => {
    if (!e.target.closest('.clock-card') && !e.target.closest('.action-panel') && !e.target.closest('.settings-panel')) {
      const toggle = document.getElementById('toggle-click-through');
      toggle.checked = !toggle.checked;
      toggle.dispatchEvent(new Event('change'));
      
      // Visual feedback via a subtle animation
      const widget = document.getElementById('clock-widget');
      widget.style.transform = `${widget.style.transform} scale(0.98)`;
      setTimeout(() => {
        widget.style.setProperty('--size-scale', state.scale / 100);
      }, 100);
    }
  });
}

// Document Picture-in-Picture API supporting browser floating always-on-top window
let pipWindow = null;
async function togglePiP() {
  if (!('documentPictureInPicture' in window)) {
    alert('Document Picture-in-Picture is not supported in your browser. Try Chrome, Edge, or running the app natively via Electron.');
    return;
  }
  
  if (pipWindow) {
    pipWindow.close();
    return;
  }
  
  try {
    const scale = state.scale / 100;
    const width = state.layout === 'horizontal' ? 480 : 180;
    const height = state.layout === 'horizontal' ? 140 : 380;
    
    pipWindow = await window.documentPictureInPicture.requestWindow({
      width: Math.round(width * scale),
      height: Math.round(height * scale),
    });
    
    // Copy stylesheets to Pip document
    [...document.styleSheets].forEach((styleSheet) => {
      try {
        const cssRules = [...styleSheet.cssRules].map((rule) => rule.cssText).join('');
        const style = document.createElement('style');
        style.textContent = cssRules;
        pipWindow.document.head.appendChild(style);
      } catch (e) {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.type = styleSheet.type;
        link.media = styleSheet.media.mediaText;
        link.href = styleSheet.href;
        pipWindow.document.head.appendChild(link);
      }
    });
    
    // Copy font links to Pip document
    document.querySelectorAll('link[rel="preconnect"], link[href*="fonts.googleapis.com"]').forEach(link => {
      pipWindow.document.head.appendChild(link.cloneNode(true));
    });
    
    // Copy body classes
    pipWindow.document.body.className = document.body.className;
    
    // Move Widget to Pip
    const widget = document.getElementById('clock-widget');
    pipWindow.document.body.appendChild(widget);
    
    // Handle PiP window close to restore widget
    pipWindow.addEventListener('unload', () => {
      pipWindow = null;
      document.getElementById('widget-container').appendChild(widget);
      applyState();
    });
  } catch (err) {
    console.error('Failed to open Picture-in-Picture window', err);
  }
}

// Initialize event listeners & controls
function initEvents() {
  // Settings Panel Toggle
  const settingsPanel = document.getElementById('settings-panel');
  
  document.getElementById('btn-settings').addEventListener('click', () => {
    state.settingsOpen = true;
    settingsPanel.classList.add('active');
    fitWindow();
  });
  
  document.getElementById('btn-settings-close').addEventListener('click', () => {
    state.settingsOpen = false;
    settingsPanel.classList.remove('active');
    fitWindow();
  });

  // Time format dropdown
  document.getElementById('select-format').addEventListener('change', (e) => {
    state.format = e.target.value;
    saveState();
    tick();
  });

  // Seconds checkbox
  document.getElementById('toggle-seconds').addEventListener('change', (e) => {
    state.showSeconds = e.target.checked;
    saveState();
    tick();
    fitWindow();
  });

  // Layout dropdown
  document.getElementById('select-layout').addEventListener('change', (e) => {
    state.layout = e.target.value;
    saveState();
    applyState();
  });

  // Opacity range slider
  const sliderOpacity = document.getElementById('slider-opacity');
  const valOpacity = document.getElementById('val-opacity');
  sliderOpacity.addEventListener('input', (e) => {
    state.opacity = e.target.value;
    valOpacity.textContent = `${state.opacity}%`;
    document.getElementById('clock-widget').style.setProperty('--glass-opacity', state.opacity / 100);
    saveState();
  });

  // Size scaling slider
  const sliderScale = document.getElementById('slider-scale');
  const valScale = document.getElementById('val-scale');
  sliderScale.addEventListener('input', (e) => {
    state.scale = e.target.value;
    valScale.textContent = `${(state.scale / 100).toFixed(2)}x`;
    document.getElementById('clock-widget').style.setProperty('--size-scale', state.scale / 100);
    saveState();
    fitWindow();
  });

  // Click-through toggle (Electron only)
  document.getElementById('toggle-click-through').addEventListener('change', (e) => {
    state.clickThrough = e.target.checked;
    
    // visual indication of click-through state
    const widget = document.getElementById('clock-widget');
    if (state.clickThrough) {
      widget.classList.add('click-through-active');
    } else {
      widget.classList.remove('click-through-active');
      if (isElectron) {
        window.electronAPI.setIgnoreMouseEvents(false);
      }
    }
    
    saveState();
  });

  // Themes grid selection
  document.querySelectorAll('.theme-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.theme-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.theme = btn.dataset.theme;
      saveState();
      applyState();
    });
  });

  // Electron Title Bar Actions
  if (isElectron) {
    document.getElementById('btn-minimize').addEventListener('click', () => {
      window.electronAPI.minimizeApp();
    });
    
    document.getElementById('btn-close').addEventListener('click', () => {
      window.electronAPI.closeApp();
    });
  } else {
    // Picture-in-picture action for browser
    document.getElementById('btn-pip').addEventListener('click', togglePiP);
  }
}

// Start application
document.addEventListener('DOMContentLoaded', () => {
  loadState();
  initEvents();
  initClickThrough();
  
  // Initial tick
  tick();
  
  // Set accurate timer: update every 200ms for smooth seconds, or 5000ms if seconds are hidden
  setInterval(() => {
    tick();
  }, 200);
});
