// Runs the demo site's week planner (frontend/src/planner.ts) on JSON from stdin, for tests/test_demo_planner.py.
import { readFileSync } from 'node:fs'
import { plan, NoSlotLeft } from '../frontend/src/planner.ts'

const { patients, changes, capacity, long_wait, week_of } = JSON.parse(readFileSync(0, 'utf8'))
try {
  process.stdout.write(JSON.stringify(plan(patients, changes, capacity, long_wait, week_of)))
} catch (e) {
  if (!(e instanceof NoSlotLeft)) throw e
  process.stdout.write(JSON.stringify({ error: e.message }))
}
