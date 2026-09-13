import { Capabilities } from './sections/Capabilities'
import { Contradiction } from './sections/Contradiction'
import { Faq } from './sections/Faq'
import { FinalCta } from './sections/FinalCta'
import { Footer } from './sections/Footer'
import { Gate } from './sections/Gate'
import { Loop } from './sections/Loop'
import { Numbers } from './sections/Numbers'
import { Problem } from './sections/Problem'
import { Provenance } from './sections/Provenance'
import { Replan } from './sections/Replan'

/** Everything after the hero, in one lazily-loaded chunk. */
export default function BelowFold() {
  return (
    <>
      <Problem />
      <Loop />
      <Contradiction />
      <Replan />
      <Capabilities />
      <Gate />
      <Provenance />
      <Numbers />
      <Faq />
      <FinalCta />
      <Footer />
    </>
  )
}
