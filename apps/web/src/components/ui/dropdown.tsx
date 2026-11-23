import { useEffect, useRef, type ReactNode } from 'react'

export function Dropdown({ label, trigger, children, header }: {
  label: string
  trigger: ReactNode
  header?: boolean
  children: (close: () => void) => ReactNode
}) {
  const ref = useRef<HTMLDetailsElement>(null)
  function close(restoreFocus = false) {
    if (!ref.current?.open) return
    ref.current.open = false
    if (restoreFocus) ref.current.querySelector('summary')?.focus()
  }

  useEffect(() => {
    function dismiss(event: PointerEvent) {
      if (event.target instanceof Node && !ref.current?.contains(event.target)) close()
    }
    document.addEventListener('pointerdown', dismiss)
    return () => document.removeEventListener('pointerdown', dismiss)
  }, [])

  return <details ref={ref} className="relative"
    onKeyDown={event => {
      if (event.key !== 'Escape' || !ref.current?.open) return
      event.stopPropagation()
      close(true)
    }}>
    <summary aria-label={label} className="flex cursor-pointer list-none items-center gap-2 rounded-lg p-2 hover:bg-muted [&::-webkit-details-marker]:hidden">{trigger}</summary>
    <div className={`z-20 mt-2 w-max min-w-40 max-w-[min(22rem,calc(100vw-2rem))] rounded-xl border border-border bg-card p-2 text-left text-foreground shadow-xl ${header ? 'fixed right-3 top-14 sm:absolute sm:right-0 sm:top-auto' : 'absolute right-0'}`}>
      {children(() => close(true))}
    </div>
  </details>
}
