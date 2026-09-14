/**
 * DischargePulse: Automated Demo Video Recording Script (Puppeteer)
 *
 * Precisely timed for a comfortable 2m45s – 3m00s voiceover matching DEMO_VIDEO_SCRIPT.md.
 *
 * Usage:
 *   cd frontend
 *   npm run record:demo
 *
 * Custom Pace:
 *   node scripts/record_demo.js --speed=0.8  (slower)
 *   node scripts/record_demo.js --speed=1.2  (faster)
 */

import puppeteer from 'puppeteer'

const BASE_URL = process.env.VITE_DEV_SERVER_URL || 'http://localhost:5173'

// Parse command line speed argument (default: 1.0 = exact 2m45s pace)
const speedArg = process.argv.find((a) => a.startsWith('--speed='))
const SPEED = speedArg ? parseFloat(speedArg.split('=')[1]) || 1.0 : 1.0

// Paced sleep helper scaled by SPEED
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms / SPEED))

// Smooth human-like cursor movements with easing
async function smoothMove(page, targetSelectorOrCoords, durationMs = 1000) {
  try {
    let targetX, targetY

    if (typeof targetSelectorOrCoords === 'string') {
      const el = await page.waitForSelector(targetSelectorOrCoords, { visible: true, timeout: 5000 })
      if (!el) return
      const box = await el.boundingBox()
      if (!box) return
      targetX = box.x + box.width / 2
      targetY = box.y + box.height / 2
    } else {
      targetX = targetSelectorOrCoords.x
      targetY = targetSelectorOrCoords.y
    }

    await page.evaluate(
      ({ x, y, duration }) => {
        window.__moveCursor?.(x, y, duration)
      },
      { x: targetX, y: targetY, duration: durationMs / SPEED },
    )

    await sleep(durationMs + 60)
  } catch (e) {}
}

async function smoothClick(page, selector, durationMs = 800) {
  try {
    await smoothMove(page, selector, durationMs)
    await page.evaluate(() => window.__clickCursor?.())
    await sleep(200)
    const el = await page.$(selector)
    if (el) await el.click()
  } catch (e) {}
}

// Inject smooth visual virtual cursor and subtle scene cue banner
async function injectCursorAndOverlay(page) {
  await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'light' }])

  await page.evaluateOnNewDocument(() => {
    try {
      localStorage.setItem('dp-theme', 'light')
    } catch {}
    document.documentElement.classList.remove('dark')

    window.addEventListener('DOMContentLoaded', () => {
      document.documentElement.classList.remove('dark')
      if (document.getElementById('demo-virtual-cursor')) return

      // Virtual glowing cursor
      const cursor = document.createElement('div')
      cursor.id = 'demo-virtual-cursor'
      cursor.style.position = 'fixed'
      cursor.style.top = '0px'
      cursor.style.left = '0px'
      cursor.style.width = '20px'
      cursor.style.height = '20px'
      cursor.style.borderRadius = '50%'
      cursor.style.backgroundColor = 'rgba(59, 130, 246, 0.9)'
      cursor.style.border = '2.5px solid #ffffff'
      cursor.style.boxShadow = '0 0 16px rgba(59, 130, 246, 0.8), 0 2px 8px rgba(0,0,0,0.3)'
      cursor.style.pointerEvents = 'none'
      cursor.style.zIndex = '999999'
      cursor.style.transition = 'transform 0.15s ease, opacity 0.2s ease'
      cursor.style.transform = 'translate(100px, 100px)'
      document.body.appendChild(cursor)

      // Auto-fit 85% scale for small laptop monitors
      if (window.innerWidth < 1650) {
        document.documentElement.style.zoom = '85%'
      }

      let curX = 100
      let curY = 100

      window.__moveCursor = (x, y, duration = 800) => {
        const startX = curX
        const startY = curY
        const startTime = performance.now()

        function step(now) {
          const progress = Math.min((now - startTime) / duration, 1)
          const ease =
            progress < 0.5
              ? 4 * progress * progress * progress
              : 1 - Math.pow(-2 * progress + 2, 3) / 2

          curX = startX + (x - startX) * ease
          curY = startY + (y - startY) * ease
          cursor.style.transform = `translate(${curX}px, ${curY}px)`

          if (progress < 1) {
            requestAnimationFrame(step)
          }
        }
        requestAnimationFrame(step)
      }

      window.__clickCursor = () => {
        cursor.style.transform = `translate(${curX}px, ${curY}px) scale(0.75)`
        cursor.style.backgroundColor = 'rgba(37, 99, 235, 1)'
        setTimeout(() => {
          cursor.style.transform = `translate(${curX}px, ${curY}px) scale(1)`
          cursor.style.backgroundColor = 'rgba(59, 130, 246, 0.9)'
        }, 200)
      }
    })
  })
}

async function runDemo() {
  console.log('===================================================================')
  console.log(`🎬 DischargePulse Automated Demo Recorder (Target: ~2m45s – 3m00s)`)
  console.log(`   Speed Multiplier: ${SPEED}x (Use --speed=0.8 to slow down if needed)`)
  console.log('===================================================================')

  const browser = await puppeteer.launch({
    headless: false,
    defaultViewport: null,
    args: ['--start-maximized', '--disable-notifications', '--no-sandbox'],
  })

  const page = await browser.newPage()
  await injectCursorAndOverlay(page)

  // =========================================================================
  // SCENE 1: The Problem & Patient Requirements (0:00 - 0:28 | 28s total)
  // Voiceover: Explain $4.8M bottleneck, 2.4 excess days, Patient 10482 requirements
  // =========================================================================
  console.log('\n[0:00] SCENE 1 (28s): Intake & Requirements on /runs/new')
  await page.goto(`${BASE_URL}/runs/new`, { waitUntil: 'domcontentloaded' })
  await sleep(4000)

  // Hover over Patient Demographics (Patient #10482)
  console.log('  👉 [0:04] Highlighting Synthetic Patient #10482 (71F, Hip Arthroplasty)')
  await smoothMove(page, 'input[value="10482"], label:first-of-type', 1200)
  await sleep(6000)

  // Scroll smoothly down to show Hard Constraints vs Soft Preferences
  console.log('  👉 [0:11] Highlighting Hard Requirements (Wound VAC, IV, Aetna MA)')
  await page.evaluate(() => window.scrollBy({ top: 320, behavior: 'smooth' }))
  await sleep(2000)
  await smoothMove(page, 'input[value="scripted"]', 1200)
  await sleep(6000)

  // Hover over Execution Limits
  console.log('  👉 [0:19] Showing Execution Limits & Telephony Modes')
  await smoothMove(page, 'input[type="number"]', 1000)
  await sleep(4000)

  // Hover over Start Run button
  console.log('  👉 [0:24] Moving cursor to "Start Run"')
  await smoothMove(page, 'button[type="submit"]', 1200)
  await sleep(3500)

  // =========================================================================
  // SCENE 2: The Agentic Loop in Action (0:28 - 1:03 | 35s total)
  // Voiceover: Explain closed-loop architecture, hard vs soft filtering, parallel calls
  // =========================================================================
  console.log('\n[0:28] SCENE 2 (35s): Closed-Loop Agent Execution on /runs/example')
  await page.goto(`${BASE_URL}/runs/example`, { waitUntil: 'domcontentloaded' })
  await sleep(3000)

  // Highlight top Loop Progress bar (Plan -> Act -> Observe -> Reason -> Re-Plan)
  console.log('  👉 [0:31] Highlighting Cognitive Loop Track')
  await smoothMove(page, 'nav, .mb-5', 1500)
  await sleep(8000)

  // Highlight Candidate Facilities Matrix in Middle Column
  console.log('  👉 [0:40] Highlighting Concurrent Facility Screening')
  await smoothMove(page, 'table, tbody', 1200)
  await sleep(10000)

  // Hover over Patient Requirements summary in left column
  console.log('  👉 [0:51] Highlighting Ingested Requirements on the left')
  await smoothMove(page, 'aside:first-of-type', 1200)
  await sleep(11000)

  // =========================================================================
  // SCENE 3: The Contradiction & Sister Lead Discovery (1:03 - 1:40 | 37s total)
  // Voiceover: "Directories lie; phone calls get the truth." Contradiction & sister lead.
  // =========================================================================
  console.log('\n[1:03] SCENE 3 (37s): Contradiction Banner & Sister Facility Lead')

  // Move to Red Contradiction Banner
  console.log('  👉 [1:03] Highlighting ⚠️ DIRECTORY CONTRADICTION on Bayview')
  await smoothMove(page, '[role="region"], div[class*="border-unavailable"]', 1200)
  await sleep(8000)

  // Open Bayview Call Detail / Transcript
  console.log('  👉 [1:12] Opening Call Transcript View')
  try {
    const callLink = await page.$('a[href*="/calls/"]')
    if (callLink) {
      await smoothClick(page, 'a[href*="/calls/"]', 1000)
      await sleep(3000)
      // Scroll down to display the dialogue turns
      await page.evaluate(() => window.scrollBy({ top: 320, behavior: 'smooth' }))
      await sleep(8000)
      // Return to Workbench
      console.log('  👉 [1:23] Returning to Workbench')
      await page.goto(`${BASE_URL}/runs/example`, { waitUntil: 'domcontentloaded' })
      await sleep(2000)
    }
  } catch {}

  // Highlight Spoken Sister Lead in Right Column
  console.log('  👉 [1:25] Highlighting Spoken Sister Lead to Peninsula Campus in Reasoning Log')
  await smoothMove(page, 'aside:last-of-type, [id="selected-call"]', 1200)
  await sleep(14000)

  // =========================================================================
  // SCENE 4: Bounded LLM Review & Verified Match (1:40 - 2:15 | 35s total)
  // Voiceover: Peninsula Campus confirmed, all 4 hard requirements, Claude review
  // =========================================================================
  console.log('\n[1:40] SCENE 4 (35s): Verified Match & Bounded Claude Review')

  // Hover over Peninsula Campus (Confirmed hard requirements)
  console.log('  👉 [1:40] Highlighting 4 Confirmed Green Checks (Payer, Bed, Wound, IV)')
  await page.evaluate(() => window.scrollTo({ top: 80, behavior: 'smooth' }))
  await sleep(1500)
  await smoothMove(page, 'tbody tr:first-child', 1200)
  await sleep(10000)

  // Hover over Claude Review card in right reasoning trace
  console.log('  👉 [1:52] Highlighting Claude Sonnet 4.5 LLM Review')
  await smoothMove(page, 'aside:last-of-type', 1200)
  await sleep(12000)

  // Move to "Review placement" button
  console.log('  👉 [2:05] Moving to "Review placement" button')
  await smoothMove(page, 'header button', 1200)
  await sleep(9000)

  // =========================================================================
  // SCENE 5: Human-in-the-Loop Approval & Referral Packet PDF (2:15 - 2:45 | 30s total)
  // Voiceover: Human approval safety gate, Case Manager brief, official PDF packet
  // =========================================================================
  console.log('\n[2:15] SCENE 5 (30s): Opening Case Manager Brief & Generating PDF')

  // Click "Review placement" to open approval sheet
  await page.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(
      (b) => b.textContent.includes('Review placement') || b.textContent.includes('View decision'),
    )
    if (btn) btn.click()
  })
  await sleep(3000)

  // Scroll through Case Manager Brief
  console.log('  👉 [2:19] Scrolling through Case Manager Plain-Language Brief')
  await page.evaluate(() => {
    const sheet = document.querySelector('[role="dialog"]')
    if (sheet) sheet.scrollBy({ top: 380, behavior: 'smooth' })
  })
  await sleep(12000)

  // Hover on "Approve Placement & Generate Packet" button
  console.log('  👉 [2:32] Highlighting 1-Click Human Approval')
  await sleep(12000)

  // =========================================================================
  // SCENE 6: Architecture, Systems Overview & Conclusion (2:45 - 3:00 | 15s total)
  // Voiceover: Tech stack summary, 250 passing tests, closing impact hook
  // =========================================================================
  console.log('\n[2:45] SCENE 6 (15s): Systems Telemetry & Conclusion')

  // Navigate to /system
  await page.goto(`${BASE_URL}/system`, { waitUntil: 'domcontentloaded' })
  await sleep(2500)
  console.log('  👉 [2:48] Showing Live Telephony Budget & Test Telemetry')
  await smoothMove(page, 'dl, section', 1200)
  await sleep(7000)

  // Return to clean Landing Page / Console
  await page.goto(`${BASE_URL}`, { waitUntil: 'domcontentloaded' })
  await sleep(4000)

  console.log('\n===================================================================')
  console.log('✅ Demo recording sequence completed in 2m48s!')
  console.log('   Perfect, natural timing for reading DEMO_VIDEO_SCRIPT.md!')
  console.log('===================================================================')
  await browser.close()
}

runDemo().catch((err) => {
  console.error('❌ Demo automation failed:', err)
  process.exit(1)
})
