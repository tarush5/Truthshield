/**
 * The landing palette. Whole surfaces take these colours (the hero, the
 * pinned section, engine cards); `ink` is the text colour that reads on each
 * one, `soft` a pale tint of it for highlights and discs.
 */
export type Colour = 'orange' | 'amber' | 'green' | 'pink' | 'blue' | 'yellow';

export const PALETTE: Record<Colour, { bg: string; ink: string; soft: string }> = {
  orange: { bg: '#E8562F', ink: '#FFF6EA', soft: '#FFD3BF' },
  amber: { bg: '#F7A41D', ink: '#4A2600', soft: '#FFE2AE' },
  green: { bg: '#5DB35A', ink: '#0F3410', soft: '#D2EFCD' },
  pink: { bg: '#F07C8E', ink: '#4A0E1C', soft: '#FFD6DD' },
  blue: { bg: '#4F5FC4', ink: '#FFF6EA', soft: '#D8DCF6' },
  yellow: { bg: '#F4D23C', ink: '#3D3000', soft: '#FFF0AE' },
};

export const ORDER: Colour[] = ['orange', 'amber', 'green', 'pink', 'blue', 'yellow'];

export const pad = (n: number) => String(n).padStart(2, '0');
