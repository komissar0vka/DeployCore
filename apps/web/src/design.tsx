import { ArrowUpRight, CircleDot, Inbox, Search, type LucideIcon } from 'lucide-react'
import { useId, type FormEvent, type ReactNode, type Ref } from 'react'
import { Badge } from './components/ui/badge'
import { Button } from './components/ui/button'
import { Dialog } from './components/ui/dialog'

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
    <div className="min-w-0">
      <h1 className="break-words text-2xl font-semibold tracking-tight sm:text-[1.85rem]">{title}</h1>
      {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
    </div>
    {actions}
  </div>
}

export function SectionTitle({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
    <div><h2 className="text-sm font-semibold sm:text-base">{title}</h2>
      {description && <p className="mt-1 text-xs text-muted-foreground">{description}</p>}
    </div>
    {actions}
  </div>
}

export function StatCard({ label, value, icon: Icon, tone = 'primary', onClick, unavailable }: {
  label: string; value?: number; icon: LucideIcon; tone?: 'primary' | 'blue' | 'green' | 'red'
  onClick?: () => void; unavailable?: string
}) {
  const colors = {
    primary: 'bg-primary-soft text-primary', blue: 'bg-info-soft text-info',
    green: 'bg-success-soft text-success', red: 'bg-danger-soft text-danger',
  }
  const content = <>
    <span className="flex items-center justify-between gap-2">
      <span className={`grid size-8 shrink-0 place-items-center rounded-lg ${colors[tone]}`}><Icon className="size-4" aria-hidden /></span>
      {onClick && <ArrowUpRight className="size-4 text-muted-foreground" aria-hidden />}
    </span>
    <span className="mt-2.5 block text-[1.65rem] leading-tight font-semibold tabular-nums">{value ?? '—'}</span>
    <span className="mt-1 block text-xs font-medium text-muted-foreground">{label}</span>
    {unavailable && <span className="mt-1 block text-[0.68rem] text-muted-foreground">{unavailable}</span>}
  </>
  const classes = 'flex min-w-0 flex-col items-stretch rounded-xl border border-border bg-card p-3.5 text-left sm:p-4'
  return onClick ? <button type="button" className={classes + ' transition-colors hover:border-ring'} onClick={onClick}>{content}</button>
    : <article className={classes}>{content}</article>
}

export function StatusBadge({ tone = 'neutral', children }: { tone?: 'neutral' | 'success' | 'warning' | 'danger'; children: ReactNode }) {
  return <Badge variant={tone}><CircleDot aria-hidden className="size-2.5 shrink-0" />{children}</Badge>
}

export function DataTable({ label, head, children }: { label: string; head: ReactNode; children: ReactNode }) {
  return <table aria-label={label} className="data-table w-full table-fixed text-left text-sm">
    <thead><tr>{head}</tr></thead><tbody>{children}</tbody>
  </table>
}

export function SearchInput({ value, onChange, onSearch, label, submitLabel, placeholder, inputRef }: {
  value: string; onChange: (value: string) => void; onSearch: (event: FormEvent<HTMLFormElement>) => void
  label: string; submitLabel: string; placeholder: string; inputRef?: Ref<HTMLInputElement>
}) {
  return <form className="relative mr-auto min-w-0 max-w-lg grow" role="search" onSubmit={onSearch}>
    <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
    <input ref={inputRef} className="input w-full pl-9 pr-12" aria-label={label} placeholder={placeholder}
      value={value} maxLength={120} onChange={event => onChange(event.target.value)} />
    <button type="submit" aria-label={submitLabel} className="absolute inset-y-0 right-1 rounded-md px-2 text-xs font-medium text-primary hover:bg-primary-soft">
      <ArrowUpRight className="size-4" aria-hidden />
    </button>
  </form>
}

export function EmptyState({ title, description, icon: Icon = Inbox, action }: {
  title: string; description?: string; icon?: LucideIcon; action?: ReactNode
}) {
  return <div className="flex min-w-0 items-start gap-3 rounded-xl border border-dashed border-border p-3.5">
    <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground"><Icon className="size-4" aria-hidden /></span>
    <div className="min-w-0">
      <p className="text-sm font-medium">{title}</p>
      {description && <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  </div>
}

export function LoadingSkeleton({ label, rows = 3 }: { label: string; rows?: number }) {
  return <div role="status" aria-label={label} className="grid gap-3 py-2">
    {Array.from({ length: rows }, (_, index) => <div aria-hidden key={index} className={`h-4 rounded bg-muted motion-safe:animate-pulse ${index === rows - 1 ? 'w-2/3' : 'w-full'}`} />)}
  </div>
}

export function ConfirmDialog({ title, description, close, confirm, labels }: {
  title: string; description: string; close: () => void; confirm: () => void
  labels: { close: string; cancel: string; confirm: string }
}) {
  return <Dialog title={title} closeLabel={labels.close} close={close}>
    <p className="text-sm leading-relaxed text-muted-foreground">{description}</p>
    <div className="mt-5 flex flex-wrap justify-end gap-2">
      <Button variant="outline" onClick={close}>{labels.cancel}</Button>
      <Button variant="destructive" onClick={confirm}>{labels.confirm}</Button>
    </div>
  </Dialog>
}

export interface ActivityItem { key: string | number; title: string; detail?: string; time: string; warning?: boolean }

export function ActivityFeed({ items }: { items: ActivityItem[] }) {
  return <ul className="divide-y divide-border">{items.map(item => <li key={item.key} className="flex min-w-0 items-start gap-2.5 py-2.5 first:pt-0 last:pb-0">
    <CircleDot aria-hidden className={`mt-1 size-3.5 shrink-0 ${item.warning ? 'text-danger' : 'text-info'}`} />
    <div className="min-w-0 grow">
      <p className="break-words text-sm font-medium">{item.title}</p>
      <div className="mt-0.5 flex flex-wrap gap-x-2 text-xs text-muted-foreground">
        {item.detail && <span className="break-all">{item.detail}</span>}
        <time dateTime={item.time}>{new Date(item.time).toLocaleString(document.documentElement.lang)}</time>
      </div>
    </div>
  </li>)}</ul>
}

export function QuickAction({ label, icon: Icon, onClick }: { label: string; icon: LucideIcon; onClick: () => void }) {
  return <button type="button" onClick={onClick} className="flex w-full items-center gap-2.5 rounded-xl border border-border px-3 py-2.5 text-left text-sm font-medium transition-colors hover:border-ring hover:bg-primary-soft">
    <Icon className="size-4 shrink-0 text-primary" aria-hidden /><span className="flex-1">{label}</span><ArrowUpRight className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
  </button>
}

export function DeviceCard({ hostname, open, status, actions, children }: {
  hostname: string; open: () => void; status: ReactNode; actions: ReactNode; children: ReactNode
}) {
  const heading = useId()
  return <article aria-labelledby={heading} className="min-w-0 rounded-xl border border-border bg-card p-3.5">
    <div className="flex min-w-0 items-start gap-2">
      <h3 id={heading} className="min-w-0 grow">
        <button type="button" className="break-all text-left text-sm font-semibold text-primary hover:underline" onClick={open}>{hostname}</button>
      </h3>
      {actions}
    </div>
    <div className="my-2">{status}</div>
    {children}
  </article>
}
