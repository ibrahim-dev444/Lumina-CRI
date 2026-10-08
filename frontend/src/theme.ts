// Light is the default. Dark only when the user picks it; the choice is remembered in this browser.

export type Theme = 'light' | 'dark'
const KEY = 'lumina-theme'

export function getTheme(): Theme {
  try {
    return localStorage.getItem(KEY) === 'dark' ? 'dark' : 'light'
  } catch {
    return 'light' // storage can be blocked (private window); fall back quietly
  }
}

export function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme
  try {
    localStorage.setItem(KEY, theme)
  } catch {
    // not saved, but the page still switches
  }
}
