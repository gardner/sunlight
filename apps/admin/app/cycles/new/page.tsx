import { createCycleAction } from "./actions";

export default function NewCyclePage() {
  return (
    <main className="shell">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Request cycles</p>
          <h1>New cycle</h1>
        </div>
        <a className="button" href="/cycles">
          Cycles
        </a>
      </header>

      <form action={createCycleAction} className="panel stack">
        <label>
          Cycle month
          <input name="cycleMonth" placeholder="2026-05" required pattern="\d{4}-\d{2}" />
        </label>
        <button className="button" type="submit">
          Create cycle
        </button>
      </form>
    </main>
  );
}
