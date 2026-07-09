/** Shared Tailwind class bundles for the cockpit UI. */
export const inputClass =
  'w-full rounded-lg border border-slate-600/30 bg-cockpit-bg px-3 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 focus:border-indigo-400/60 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 light:border-slate-300 light:bg-white light:text-slate-900 light:placeholder:text-slate-400'

export const selectClass =
  'rounded-lg border border-slate-600/30 bg-cockpit-bg px-2.5 py-2 text-sm text-slate-100 focus:border-indigo-400/60 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 light:border-slate-300 light:bg-white light:text-slate-900'

export const labelClass =
  'text-sm font-semibold text-slate-400 light:text-slate-600'

export const btnPrimaryClass =
  'inline-flex items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:brightness-105 disabled:cursor-default disabled:opacity-55 disabled:shadow-none'

export const cardClass =
  'rounded-xl border border-slate-600/20 bg-cockpit-surface/80 p-4 light:border-slate-200 light:bg-white light:shadow-sm light:shadow-slate-200/50'

export const providerToneClass: Record<string, string> = {
  violet: 'bg-violet-500/20 text-violet-300 light:bg-violet-500/15 light:text-violet-700',
  emerald: 'bg-emerald-500/20 text-emerald-300 light:bg-emerald-500/15 light:text-emerald-700',
  indigo: 'bg-indigo-500/20 text-indigo-300 light:bg-indigo-500/15 light:text-indigo-700',
  amber: 'bg-amber-500/20 text-amber-300 light:bg-amber-500/15 light:text-amber-700',
  sky: 'bg-sky-500/20 text-sky-300 light:bg-sky-500/15 light:text-sky-700',
}
