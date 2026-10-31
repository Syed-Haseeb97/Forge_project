import React from 'react'

export default function Brand({ className = '', imgClassName = 'h-9 sm:h-10' }) {
  return (
    <span className={`inline-flex items-center text-left group ${className}`} aria-label="Jan Aawaz Home">
      {/* Light Theme Logo */}
      <img
        src="/logo-light.jpg"
        alt="जनAawaz"
        className={`${imgClassName} w-auto object-contain rounded-lg dark:hidden transition-transform duration-200 group-hover:scale-102`}
        loading="eager"
      />
      {/* Dark Theme Logo */}
      <img
        src="/logo-dark.jpg"
        alt="जनAawaz"
        className={`${imgClassName} w-auto object-contain rounded-lg hidden dark:block transition-transform duration-200 group-hover:scale-102`}
        loading="eager"
      />
    </span>
  )
}
