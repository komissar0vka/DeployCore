import { X } from 'lucide-react'
import { useEffect, useId, useRef, type PropsWithChildren } from 'react'

export function Dialog({ title, close, closeLabel, children, drawer }: PropsWithChildren<{
  title: string
  drawer?: boolean
  close: () => void
  closeLabel: string
}>) {
  const element = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  useEffect(() => {
    const dialog = element.current
    dialog?.showModal()
    return () => dialog?.close()
  }, [])
  return <dialog ref={element} aria-labelledby={titleId}
    onCancel={event => { event.preventDefault(); close() }}
    className={`overflow-auto border border-border p-5 shadow-xl backdrop:bg-slate-950/65 sm:p-6 ${drawer ? "drawer-dialog" : "m-auto max-h-[calc(100dvh-2rem)] w-[min(32rem,calc(100%-2rem))] rounded-xl bg-card text-foreground"}`}>
    <div className="mb-4 flex items-start justify-between gap-3">
      <h2 id={titleId} className="text-lg font-semibold">{title}</h2>
      <button type="button" className="rounded-md p-1 hover:bg-muted" onClick={close} aria-label={closeLabel} autoFocus>
        <X className="size-5" aria-hidden />
      </button>
    </div>
    {children}
  </dialog>
}
