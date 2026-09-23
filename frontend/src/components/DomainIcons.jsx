/**
 * A fixed mark for every legal regime and pipeline concept the app talks
 * about, so the same idea always wears the same icon — in a chip, in a nav
 * item, on a source card, in the hero thread. A judge scanning the applicable
 * areas should be able to read the regime mix without reading the words.
 *
 * Keys match the backend's own vocabulary (see COPY.areaLabels), and lookups
 * fall back to a neutral mark, so an unmapped area added server-side renders
 * correctly instead of crashing the panel.
 */
import {
  BarChart3, Copyright, Droplet, FileCheck2, Gavel, Leaf, Lock, MapPin,
  Megaphone, PenTool, Pill, PlugZap, Scale, ScrollText, Share2, ShieldCheck,
  Sparkles, Sprout, Stamp, Tag, Tags, Utensils, Waypoints,
} from 'lucide-react'

/** Applicable IP & regulatory areas returned in result.applicable_areas. */
export const AREA_ICON = {
  Patents: Stamp,
  'Geographical Indications': MapPin,
  Trademarks: Tag,
  Copyright: Copyright,
  Designs: PenTool,
  'Trade Secrets': Lock,
  'Plant Variety Protection': Sprout,
  'Traditional Knowledge': ScrollText,
  'Access-and-Benefit-Sharing': Share2,
  'Drug regulation': Pill,
  Advertising: Megaphone,
  Labelling: Tags,
  'Food / nutraceutical regulation': Utensils,
  'Cosmetic regulation': Droplet,
}

export function areaIcon(area) {
  return AREA_ICON[area] || Scale
}

/** The five pipeline stages, in order. */
const STAGE_ICONS = [Leaf, FileCheck2, Stamp, Gavel, ScrollText]

export function stageIcon(index) {
  return STAGE_ICONS[index] || Scale
}

/** Primary navigation — mirrors each tool's own header icon. */
const NAV_ICONS = {
  analyze: Sparkles,
  abs: ShieldCheck,
  tkdl: ScrollText,
  graph: Waypoints,
  connectors: PlugZap,
  eval: BarChart3,
}

export function navIcon(tab) {
  return NAV_ICONS[tab] || Scale
}
