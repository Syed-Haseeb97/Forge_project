import React from 'react'

export default function Brand({ className = '', imgClassName = 'h-9 sm:h-10', variant = 'full' }) {
  if (variant === 'icon') {
    return (
      <span className={`inline-flex items-center group ${className}`} aria-label="जनAawaz">
        <img
          src="/jan-icon-light.png"
          alt="जन"
          className="size-8 sm:size-9 object-contain rounded-lg shadow-sm border border-black/5 dark:hidden transition-transform duration-200 group-hover:scale-105"
        />
        <img
          src="/jan-icon-dark.png"
          alt="जन"
          className="size-8 sm:size-9 object-contain rounded-lg shadow-sm border border-white/10 hidden dark:block transition-transform duration-200 group-hover:scale-105"
        />
      </span>
    )
  }

  return (
    <span className={`inline-flex items-center text-left group ${className}`} aria-label="Jan Aawaz Home">
      {/* Light Theme Logo - Real Image Asset */}
      <img
        src="/logo-light.jpg"
        alt="जनAawaz"
        className={`${imgClassName} w-auto object-contain rounded-lg dark:hidden transition-transform duration-200 group-hover:scale-102`}
        loading="eager"
      />
      {/* Dark Theme Logo - Real Image Asset */}
      <img
        src="/logo-dark.jpg"
        alt="जनAawaz"
        className={`${imgClassName} w-auto object-contain rounded-lg hidden dark:block transition-transform duration-200 group-hover:scale-102`}
        loading="eager"
      />
    </span>
  )
}
