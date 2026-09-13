import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export interface Crumb {
  label: string
  to?: string
}

const CrumbContext = createContext<{ crumbs: Crumb[]; setCrumbs: (crumbs: Crumb[]) => void }>({
  crumbs: [],
  setCrumbs: () => {},
})

export function CrumbProvider({ children }: { children: ReactNode }) {
  const [crumbs, setCrumbs] = useState<Crumb[]>([])
  return <CrumbContext.Provider value={{ crumbs, setCrumbs }}>{children}</CrumbContext.Provider>
}

export function useCrumbState() {
  return useContext(CrumbContext).crumbs
}

/** Pages declare their breadcrumb; the top bar renders it. */
export function useCrumbs(crumbs: Crumb[]) {
  const { setCrumbs } = useContext(CrumbContext)
  const signature = crumbs.map((c) => `${c.label}|${c.to ?? ''}`).join('>')
  useEffect(() => {
    setCrumbs(crumbs)
    document.title = crumbs.length ? `${crumbs[crumbs.length - 1].label} · DischargePulse` : 'DischargePulse'
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature, setCrumbs])
}
