import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'
import type { ComponentProps } from 'react'
import { twMerge } from 'tailwind-merge'

const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium',
  {
    variants: {
      variant: {
        neutral: 'border-border bg-muted text-foreground',
        success: 'border-success-line bg-success-soft text-success',
        danger: 'border-danger-line bg-danger-soft text-danger',
        warning: 'border-warning-line bg-warning-soft text-warning',
      },
    },
    defaultVariants: { variant: 'neutral' },
  },
)

export function Badge({
  className,
  variant,
  ...props
}: ComponentProps<'span'> & VariantProps<typeof badgeVariants>) {
  return <span className={twMerge(clsx(badgeVariants({ variant }), className))} {...props} />
}
