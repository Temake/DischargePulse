import { forwardRef, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

const control =
  'w-full rounded-field border border-hairline bg-surface px-3 text-[15px] text-ink placeholder:text-ink-muted transition-colors hover:border-ink-muted/40 focus-visible:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/25 disabled:opacity-50'

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...props },
  ref,
) {
  return <input ref={ref} className={cn(control, 'h-11 pointer-fine:h-10', className)} {...props} />
})

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...props }, ref) {
    return <textarea ref={ref} className={cn(control, 'min-h-24 py-2.5 leading-relaxed', className)} {...props} />
  },
)

/** Label above, control, helper or error below. Never a placeholder as label. */
export function Field({
  label,
  htmlFor,
  hint,
  error,
  children,
  className,
}: {
  label: ReactNode
  htmlFor: string
  hint?: ReactNode
  error?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn('grid gap-1.5', className)}>
      <label htmlFor={htmlFor} className="text-sm font-medium">
        {label}
      </label>
      {children}
      {error ? (
        <p id={`${htmlFor}-error`} className="text-[13px] text-unavailable">
          {error}
        </p>
      ) : hint ? (
        <p id={`${htmlFor}-hint`} className="text-[13px] text-ink-muted">
          {hint}
        </p>
      ) : null}
    </div>
  )
}
