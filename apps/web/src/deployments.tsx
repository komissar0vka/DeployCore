import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ListTodo, Plus } from 'lucide-react'
import { useRef, useState, type FormEvent } from 'react'
import { api, type Session } from './api'
import { Dialog } from './components/ui/dialog'
import { ActivityFeed, ConfirmDialog, EmptyState, LoadingSkeleton, SectionTitle, StatusBadge } from './design'
import { Action, Field, FormError, Panel, errorMessage, type Translate } from './ui'

type Operation = 'install' | 'uninstall'
type TargetState = 'queued' | 'leased' | 'running' | 'not_executed' | 'cancelled' | 'failed'
interface Job {
  id: string; package_name: string; version: string; operation: Operation; created_at: string
  counts: Partial<Record<TargetState, number>>
}
interface Target {
  id: string; hostname: string; state: TargetState; cancel_requested: boolean
  attempt: number | null; lease_expires_at: string | null; recovery_required: boolean
}
interface Entry { id: number; target_id: string | null; action: string; created_at: string }
interface Device { id: string; hostname: string; online: boolean; agent_revoked: boolean }
interface Product { id: string; name: string }
interface Version { id: string; version: string; architecture: string; approved_at: string | null; uninstall_args: string[] | null }
interface Props { session: Session; t: Translate }
interface Input { version_id: string; operation: Operation; device_ids: string[]; request_id: string }
const pageSize = 25

function stateLabel(state: TargetState, t: Translate) {
  return {
    queued: t('В очереди', 'Queued'), leased: t('Выдано', 'Leased'), running: t('Подтверждено', 'Acknowledged'),
    cancelled: t('Отменено', 'Cancelled'), not_executed: t('Без запуска', 'Not executed'),
    failed: t('Сбой доставки', 'Delivery failed'),
  }[state]
}

function operationLabel(operation: Operation, t: Translate) {
  return operation === 'install' ? t('Установка', 'Install') : t('Удаление', 'Uninstall')
}

function JobProgress({ job, t }: { job: Job; t: Translate }) {
  const total = Object.values(job.counts).reduce((sum, count) => sum + count, 0)
  const complete = (job.counts.not_executed ?? 0) + (job.counts.cancelled ?? 0) + (job.counts.failed ?? 0)
  return <div className="grid gap-1.5 text-xs text-muted-foreground">
    <span>{t('Завершено целей', 'Targets finished')}: {complete}/{total}</span>
    <progress className="h-1.5 w-full max-w-xs accent-primary" value={complete} max={Math.max(1, total)}
      aria-label={t('Прогресс обработки', 'Processing progress')} />
    <div className="flex flex-wrap gap-2">{Object.entries(job.counts).map(([state, count]) =>
      <span key={state}>{stateLabel(state as TargetState, t)}: {count}</span>)}</div>
  </div>
}

function NewJob({ session, t, close, created }: Props & { close: () => void; created: (id: string) => void }) {
  const [packageTerm, setPackageTerm] = useState('')
  const [packageId, setPackageId] = useState('')
  const [versionId, setVersionId] = useState('')
  const [operation, setOperation] = useState<Operation>('install')
  const [term, setTerm] = useState('')
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState(new Map<string, string>())
  const submission = useRef<{ fingerprint: string; requestId: string } | null>(null)

  const products = useQuery({
    queryKey: ['job-products', packageTerm],
    queryFn: () => api<{ items: Product[] }>(`/packages?${new URLSearchParams({ q: packageTerm, limit: '25' })}`),
  })
  const versions = useQuery({
    queryKey: ['job-versions', packageId], enabled: Boolean(packageId),
    queryFn: () => api<{ versions: Version[] }>('/packages/' + packageId),
  })
  const computers = useQuery({
    queryKey: ['job-devices', term, offset],
    queryFn: () => api<{ items: Device[]; total: number }>(`/devices?${new URLSearchParams({ q: term, offset: String(offset), limit: String(pageSize) })}`),
  })
  const eligible = (versions.data?.versions ?? []).filter(version => version.approved_at && (operation === 'install' || version.uninstall_args !== null))
  const canSubmit = eligible.some(version => version.id === versionId) && selected.size > 0
  const mutation = useMutation({
    mutationFn: (body: Input) => api<Job>('/deployments', { method: 'POST', body, csrf: session.csrf_token }),
    onSuccess: job => created(job.id),
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canSubmit || mutation.isPending) return
    const payload = { version_id: versionId, operation, device_ids: [...selected.keys()].sort() }
    const fingerprint = JSON.stringify(payload)
    if (submission.current?.fingerprint !== fingerprint) {
      submission.current = { fingerprint, requestId: crypto.randomUUID() }
    }
    mutation.mutate({ ...payload, request_id: submission.current.requestId })
  }

  function toggle(device: Device) {
    setSelected(current => {
      const next = new Map(current)
      if (next.has(device.id)) next.delete(device.id)
      else if (next.size < 100) next.set(device.id, device.hostname)
      return next
    })
  }

  return <Dialog title={t('Новое задание', 'New job')} closeLabel={t('Закрыть', 'Close')} close={close}>
    <form className="grid gap-3" onSubmit={submit}>
      <p className="text-sm text-muted-foreground">{t('Режим проверки протокола. Установщик не запускается.', 'Transport validation mode. No installer is run.')}</p>
      <label className="grid gap-2 text-sm">{t('Операция', 'Operation')}
        <select aria-label={t('Операция', 'Operation')} className="input" value={operation} onChange={event => {
          setOperation(event.target.value as Operation); setVersionId('')
        }}>
          <option value="install">{operationLabel('install', t)}</option>
          <option value="uninstall">{operationLabel('uninstall', t)}</option>
        </select>
      </label>
      <Field label={t('Поиск программы', 'Search programs')} maxLength={160} value={packageTerm} onChange={event => {
        setPackageTerm(event.target.value); setPackageId(''); setVersionId('')
      }} />
      <label className="grid gap-2 text-sm">{t('Программа', 'Program')}
        <select aria-label={t('Программа', 'Program')} className="input" required value={packageId} onChange={event => {
          setPackageId(event.target.value); setVersionId('')
        }}>
          <option value="">{t('Выберите программу', 'Select a program')}</option>
          {products.data?.items.map(product => <option key={product.id} value={product.id}>{product.name}</option>)}
        </select>
      </label>
      <label className="grid gap-2 text-sm">{t('Утверждённая версия', 'Approved version')}
        <select aria-label={t('Утверждённая версия', 'Approved version')} className="input" required disabled={!eligible.length}
          value={versionId} onChange={event => setVersionId(event.target.value)}>
          <option value="">{t('Выберите версию', 'Select a version')}</option>
          {eligible.map(version => <option key={version.id} value={version.id}>{version.version} · {version.architecture}</option>)}
        </select>
      </label>
      {versions.data && !eligible.length && <p className="text-sm text-muted-foreground">
        {t('Для этой операции нет утверждённых версий.', 'There are no approved versions for this operation.')}
      </p>}
      <Field label={t('Имя, FQDN или IP устройства', 'Device hostname, FQDN or IP')} maxLength={120}
        value={term} onChange={event => { setTerm(event.target.value); setOffset(0) }} />
      {computers.isPending && <LoadingSkeleton label={t('Загрузка устройств', 'Loading devices')} />}
      <ul className="max-h-36 overflow-y-auto rounded-lg border border-border p-2 text-sm">
        {computers.data?.items.map(device => <li key={device.id}>
          <label className="flex items-center gap-2 py-1">
            <input type="checkbox" checked={selected.has(device.id)} disabled={device.agent_revoked || (selected.size === 100 && !selected.has(device.id))}
              onChange={() => toggle(device)} />
            <span className="min-w-0 grow break-all">{device.hostname}</span>
            <span className="text-xs text-muted-foreground">{device.agent_revoked ? t('Отозван', 'Revoked') : device.online ? t('Онлайн', 'Online') : t('Офлайн', 'Offline')}</span>
          </label>
        </li>)}
        {computers.data?.items.length === 0 && <li className="py-1 text-muted-foreground">{t('Устройства не найдены', 'No devices found')}</li>}
      </ul>
      {(offset > 0 || (computers.data?.total ?? 0) > pageSize) && <div className="flex flex-wrap gap-2">
        <Action secondary disabled={offset === 0} onClick={() => setOffset(offset - pageSize)}>{t('Предыдущая', 'Previous')}</Action>
        <Action secondary disabled={offset + pageSize >= (computers.data?.total ?? 0)} onClick={() => setOffset(offset + pageSize)}>{t('Следующая', 'Next')}</Action>
      </div>}
      <p className="text-sm text-muted-foreground">{t('Выбрано устройств', 'Selected devices')}: {selected.size}/100</p>
      {selected.size > 0 && <p className="max-h-16 overflow-y-auto break-words text-xs text-muted-foreground">
        {[...selected.values()].join(', ')}
      </p>}
      <FormError message={(products.error || versions.error || computers.error || mutation.error) &&
        errorMessage(products.error || versions.error || computers.error || mutation.error, t)} />
      <Action type="submit" disabled={!canSubmit || mutation.isPending}>{t('Создать задание', 'Create job')}</Action>
    </form>
  </Dialog>
}

function JobDetails({ session, t, id, back }: Props & { id: string; back: () => void }) {
  const path = '/deployments/' + id
  const query = useQuery({ queryKey: ['deployments', id], queryFn: () => api<Job & { targets: Target[] }>(path), refetchInterval: 5000 })
  const [before, setBefore] = useState<number>()
  const events = useQuery({
    queryKey: ['deployment-events', id, before],
    queryFn: () => api<Entry[]>(path + '/events' + (before ? '?before=' + before : '')),
    refetchInterval: before ? false : 5000,
  })
  const [confirm, setConfirm] = useState(false)
  const client = useQueryClient()
  const cancel = useMutation({
    mutationFn: () => api<Job>(path + '/cancel', { method: 'POST', csrf: session.csrf_token }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['deployments'] })
      void client.invalidateQueries({ queryKey: ['deployment-events', id] })
    },
  })
  const job = query.data
  const names = new Map(job?.targets.map(target => [target.id, target.hostname]))
  const eventsLabels: Record<string, string> = {
    created: t('Задание создано', 'Job created'), leased: t('Попытка выдана', 'Attempt leased'),
    acknowledged: t('Получение подтверждено', 'Delivery acknowledged'), lease_expired: t('Срок выдачи истёк', 'Lease expired'),
    recovered: t('Связь восстановлена', 'Lease recovered'), delivery_failed: t('Исчерпаны попытки выдачи', 'Delivery attempts exhausted'),
    not_executed: t('Проверка завершилась без запуска', 'Transport test completed without execution'),
    cancel_requested: t('Запрошена отмена', 'Cancellation requested'), cancelled: t('Отменено', 'Cancelled'),
  }
  return <div className="grid gap-4">
    <Action secondary onClick={back}>{t('К очереди', 'Back to queue')}</Action>
    {query.isPending && <LoadingSkeleton label={t('Загрузка задания', 'Loading job')} />}
    <FormError message={(query.error || cancel.error) && errorMessage(query.error || cancel.error, t)} />
    {job && <Panel>
      <SectionTitle title={`${job.package_name} · ${job.version}`} description={operationLabel(job.operation, t)} actions={
        session.user.role !== 'viewer' && job.targets.some(target => target.state === 'queued' || target.state === 'leased' ||
          (target.state === 'running' && !target.cancel_requested))
          ? <Action secondary disabled={cancel.isPending} onClick={() => setConfirm(true)}>{t('Отменить задание', 'Cancel job')}</Action> : undefined
      } />
      <JobProgress job={job} t={t} />
      <ul className="mt-4 divide-y divide-border">{job.targets.map(target => <li key={target.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
        <span className="break-all font-medium">{target.hostname}</span>
        <div className="flex flex-wrap items-center gap-2">
          {target.attempt && <span className="text-xs text-muted-foreground">{t('Попытка', 'Attempt')} {target.attempt}</span>}
          {target.recovery_required && <StatusBadge tone="warning">{t('Ожидается восстановление', 'Recovery required')}</StatusBadge>}
          {target.state === 'running' && target.cancel_requested && <StatusBadge tone="warning">{t('Запрошена отмена', 'Cancellation requested')}</StatusBadge>}
          <StatusBadge tone={target.state === 'failed' ? 'danger' : 'neutral'}>{stateLabel(target.state, t)}</StatusBadge>
        </div>
      </li>)}</ul>
    </Panel>}
    <Panel>
      <SectionTitle title={t('История событий', 'Event history')} />
      {events.isPending && <LoadingSkeleton label={t('Загрузка истории', 'Loading history')} />}
      <FormError message={events.error && errorMessage(events.error, t)} />
      {events.data?.length === 0 && <EmptyState title={t('Событий нет', 'No events')} />}
      {events.data && <ActivityFeed items={events.data.map(entry => ({
        key: entry.id, title: eventsLabels[entry.action] ?? entry.action,
        detail: entry.target_id ? names.get(entry.target_id) : undefined, time: entry.created_at,
      }))} />}
      <div className="mt-3 flex flex-wrap gap-2">
        {before && <Action secondary onClick={() => setBefore(undefined)}>{t('К последним', 'Latest')}</Action>}
        {events.data?.length === 50 && <Action secondary onClick={() => setBefore(events.data?.at(-1)?.id)}>{t('Более ранние события', 'Earlier events')}</Action>}
      </div>
    </Panel>
    {confirm && <ConfirmDialog title={t('Отменить задание?', 'Cancel job?')}
      description={t('Ожидающие выдачи отменятся. Подтверждённые попытки получат запрос отмены и завершатся после ответа агента.', 'Pending deliveries cancel immediately. Acknowledged attempts receive a cancellation request and wait for the agent.') }
      labels={{ close: t('Закрыть', 'Close'), cancel: t('Назад', 'Back'), confirm: t('Отменить задание', 'Cancel job') }}
      close={() => setConfirm(false)} confirm={() => { setConfirm(false); cancel.mutate() }} />}
  </div>
}

export function DeploymentsPage({ session, t }: Props) {
  const [selected, setSelected] = useState<string>()
  const [creating, setCreating] = useState(false)
  const [offset, setOffset] = useState(0)
  const client = useQueryClient()
  const list = useQuery({
    queryKey: ['deployments', 'list', offset], enabled: !selected, refetchInterval: 5000,
    queryFn: () => api<{ items: Job[]; total: number }>(`/deployments?offset=${offset}&limit=${pageSize}`),
  })
  if (selected) return <JobDetails session={session} t={t} id={selected} back={() => setSelected(undefined)} />
  return <Panel>
    <SectionTitle title={t('Очередь развёртывания', 'Deployment queue')}
      description={t('Проверка доставки и результатов без запуска установщиков.', 'Delivery and results validation without running installers.')}
      actions={session.user.role !== 'viewer' && <Action onClick={() => setCreating(true)}><Plus className="size-4" aria-hidden />{t('Новое задание', 'New job')}</Action>} />
    {list.isPending && <LoadingSkeleton label={t('Загрузка очереди', 'Loading queue')} />}
    <FormError message={list.error && errorMessage(list.error, t)} />
    {list.data?.items.length === 0 && <EmptyState icon={ListTodo} title={t('Заданий пока нет', 'No jobs yet')} />}
    <ul className="divide-y divide-border">{list.data?.items.map(job => <li key={job.id} className="grid items-start gap-2 py-3 sm:grid-cols-2">
      <div>
        <button type="button" className="break-words text-left text-sm font-semibold text-primary hover:underline"
          onClick={() => setSelected(job.id)}>{job.package_name} · {job.version}</button>
        <p className="mt-1 text-xs text-muted-foreground">{operationLabel(job.operation, t)} · {new Date(job.created_at).toLocaleString()}</p>
      </div>
      <JobProgress job={job} t={t} />
    </li>)}</ul>
    {(offset > 0 || (list.data?.total ?? 0) > pageSize) && <div className="mt-3 flex flex-wrap gap-2">
      <Action secondary disabled={offset === 0} onClick={() => setOffset(offset - pageSize)}>{t('Предыдущая', 'Previous')}</Action>
      <Action secondary disabled={offset + pageSize >= (list.data?.total ?? 0)} onClick={() => setOffset(offset + pageSize)}>{t('Следующая', 'Next')}</Action>
    </div>}
    {creating && <NewJob session={session} t={t} close={() => setCreating(false)} created={id => {
      setCreating(false); setSelected(id); void client.invalidateQueries({ queryKey: ['deployments'] })
    }} />}
  </Panel>
}
