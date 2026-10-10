import { LogoArt } from './Loader'

// Lumina's logo: three records (violet, pink, teal) overlap, and a white core lights up where they agree.
// public/favicon.svg is the same drawing for the browser tab.
export function BrandMark({ size = 32 }: { size?: number }) {
  return <LogoArt kind="overlap" size={size} animated={false} />
}
