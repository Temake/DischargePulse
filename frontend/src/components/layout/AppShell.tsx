import type { ReactNode } from 'react'
import { Header } from './Header'

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <Header />
      <main className="p-6">{children}</main>
    </div>
  )
}
