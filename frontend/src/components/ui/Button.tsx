import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { Link, type LinkProps } from 'react-router'

import { cn } from '@/lib/utils'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'quiet-danger'
export type ButtonSize = 'md' | 'sm'

const base =
  'inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-field font-medium transition-[background-color,border-color,color,transform] duration-150 active:translate-y-px disabled:pointer-events-none disabled:opacity-45'

const variants: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-white hover:bg-[color-mix(in_oklab,var(--color-accent),black_12%)] dark:text-[#0c0f11] dark:hover:bg-[color-mix(in_oklab,var(--color-accent),white_12%)]',
  secondary: 'border border-hairline bg-surface text-ink hover:border-ink-muted/40 hover:bg-surface-2',
  ghost: 'text-ink hover:bg-surface-2',
  'quiet-danger': 'border border-hairline bg-surface text-ink hover:border-unavailable/50 hover:text-unavailable',
}

// 44px on touch screens; the dense app drops to 36px only where a fine pointer is present.
const sizes: Record<ButtonSize, string> = {
  md: 'h-11 px-4 text-[15px]',
  sm: 'h-11 px-3 text-sm pointer-fine:h-9',
}

export function buttonClass(variant: ButtonVariant = 'primary', size: ButtonSize = 'md', className?: string) {
  return cn(base, variants[variant], sizes[size], className)
}

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize }
>(function Button({ variant = 'primary', size = 'md', className, type = 'button', ...props }, ref) {
  return <button ref={ref} type={type} className={buttonClass(variant, size, className)} {...props} />
})

export function ButtonLink({
  variant = 'primary',
  size = 'md',
  className,
  children,
  ...props
}: LinkProps & { variant?: ButtonVariant; size?: ButtonSize; children: ReactNode }) {
  return (
    <Link className={buttonClass(variant, size, className)} {...props}>
      {children}
    </Link>
  )
}

/** Square icon-only button. Always pass an aria-label. */
export const IconButton = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement>>(
  function IconButton({ className, type = 'button', ...props }, ref) {
    return (
      <button
        ref={ref}
        type={type}
        className={cn(
          'inline-grid size-11 shrink-0 place-items-center rounded-field text-ink-muted transition-colors hover:bg-surface-2 hover:text-ink pointer-fine:size-9',
          className,
        )}
        {...props}
      />
    )
  },
)
