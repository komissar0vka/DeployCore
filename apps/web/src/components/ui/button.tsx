import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'
import type { ComponentProps } from 'react'
import { twMerge } from 'tailwind-merge'

const buttonVariants = cva(
  'inline-flex w-fit items-center justify-center gap-2 rounded-xl px-3.5 py-2 transition-colors text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60',
  {
    variants: {
      variant: {
        default: 'bg-accent text-primary-foreground hover:bg-primary-hover',
        outline: 'border border-border bg-card text-foreground hover:bg-muted',
        destructive: 'border border-danger-line bg-danger-soft text-danger hover:border-danger',
      },
    },
    defaultVariants: { variant: 'default' },
  },
)

export function Button({ className, variant, type = 'button', ...props }: ComponentProps<'button'> & VariantProps<typeof buttonVariants>) {
  return <button type={type} data-slot="button" className={twMerge(clsx(buttonVariants({ variant }), className))} {...props} />
}
