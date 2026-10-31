import {
  Car,
  Landmark,
  Droplets,
  Factory,
  Lightbulb,
  Trash2,
  Waves,
  FileText
} from 'lucide-react'

export const CATEGORY_ICON_MAP = {
  road_damage: Car,
  bridge_damage: Landmark,
  water_leak: Droplets,
  pollution: Factory,
  streetlight: Lightbulb,
  garbage: Trash2,
  drainage: Waves,
  other: FileText,
}

export default function CategoryIcon({ category, size = 16, className = '' }) {
  const IconComponent = CATEGORY_ICON_MAP[category] || FileText
  return <IconComponent size={size} className={className} />
}
