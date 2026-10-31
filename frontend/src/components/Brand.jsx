import React from 'react'
import CivicIcon from './CivicIcon'

export default function Brand() {
  return (
    <span className="flex items-center gap-3 text-left group" aria-label="CivicLine home">
      <span className="flex size-10 items-center justify-center rounded-full bg-[#0d3035] text-[#e5b95c] shadow-sm transition-transform group-hover:scale-105">
        <CivicIcon name="shield" size={22} />
      </span>
      <span>
        <span className="block font-serif text-[22px] font-bold leading-none text-[#0d3035] dark:text-[#f6f4ee]">
          CivicLine
        </span>
        <span className="mt-1 block text-[9px] font-bold tracking-[0.18em] text-[#6f7f7d] dark:text-[#95a9a6]">
          PUBLIC GRIEVANCE PORTAL
        </span>
      </span>
    </span>
  )
}
