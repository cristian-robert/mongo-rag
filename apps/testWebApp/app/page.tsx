const facts: { label: string; value: string }[] = [
  { label: "Discovered", value: "1901, off Antikythera, Greece" },
  { label: "Estimated date", value: "c. 150–100 BCE" },
  { label: "Recovered fragments", value: "82" },
  { label: "Known gears", value: "≥ 30 bronze gears" },
];

const sections: { tag: string; title: string; body: string }[] = [
  {
    tag: "Discovery",
    title: "Salvaged from a Roman-era shipwreck",
    body:
      "Sponge divers sheltering from a storm near the small island of Antikythera found a sunken cargo ship of marble statues, amphorae, and one corroded lump of bronze. For decades the lump sat in the National Archaeological Museum in Athens, mistaken for an ornament. When it cracked open, gear teeth appeared inside — too precise, too small, and far too old to be from the era anyone expected.",
  },
  {
    tag: "Mechanism",
    title: "An analog model of the cosmos",
    body:
      "Behind a hand-cranked input, a train of bronze gears computed the positions of the Sun and Moon, the phase of the Moon, the dates of eclipses (using the Saros cycle), and the four-year cycle of the Olympic Games. A pin-and-slot pair on one wheel reproduces the Moon's elliptical orbit — a mechanical implementation of variable speed nearly two millennia before Kepler.",
  },
  {
    tag: "Significance",
    title: "Rewriting the timeline of technology",
    body:
      "Nothing of comparable complexity is known for the next thousand years. The mechanism shows that Hellenistic engineers possessed gear-cutting precision, astronomical theory, and the abstraction needed to encode both into hardware. It is less a curiosity than a reminder: the past is full of lost branches of knowledge we know only because one of them sank.",
  },
];

const timeline: { year: string; event: string }[] = [
  { year: "c. 150 BCE", event: "Mechanism likely built, possibly on Rhodes." },
  { year: "c. 65 BCE", event: "Cargo ship founders off Antikythera." },
  { year: "1901", event: "Sponge divers recover wreckage; lump enters Athens museum." },
  { year: "1951", event: "Derek de Solla Price begins systematic study." },
  { year: "2006", event: "X-ray tomography reveals dense interior gearing and inscriptions." },
  { year: "2021", event: "UCL team publishes a full computational model of the front display." },
];

export default function Home() {
  return (
    <main className="flex-1">
      <article className="mx-auto max-w-3xl px-6 py-20 sm:py-28">
        <header className="border-b border-rule pb-12">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-accent">
            Object study · No. 01
          </p>
          <h1 className="mt-6 font-display text-5xl leading-[1.05] tracking-tight text-foreground sm:text-6xl">
            The Antikythera
            <span className="block italic font-light text-accent"> Mechanism</span>
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted">
            A hand-cranked bronze device, recovered from a shipwreck in 1901, that
            modeled the heavens with gears centuries before any comparable instrument
            is known to exist. It is the oldest analog computer we have found.
          </p>

          <dl className="mt-10 grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2">
            {facts.map((f) => (
              <div key={f.label} className="flex items-baseline gap-3">
                <dt className="font-mono text-[11px] uppercase tracking-widest text-muted">
                  {f.label}
                </dt>
                <dd className="text-sm text-foreground">{f.value}</dd>
              </div>
            ))}
          </dl>
        </header>

        <section className="mt-16 space-y-16">
          {sections.map((s, i) => (
            <div key={s.tag} className="grid grid-cols-[auto_1fr] gap-x-8">
              <div className="font-mono text-xs uppercase tracking-[0.18em] text-muted">
                <span className="text-accent">{String(i + 1).padStart(2, "0")}</span>
                <span className="block mt-1">{s.tag}</span>
              </div>
              <div>
                <h2 className="font-display text-2xl tracking-tight sm:text-3xl">
                  {s.title}
                </h2>
                <p className="mt-4 text-base leading-7 text-foreground/85">{s.body}</p>
              </div>
            </div>
          ))}
        </section>

        <section className="mt-20">
          <h2 className="font-mono text-xs uppercase tracking-[0.2em] text-accent">
            Timeline
          </h2>
          <ol className="mt-6 divide-y divide-rule border-y border-rule">
            {timeline.map((t) => (
              <li
                key={t.year}
                className="grid grid-cols-[7rem_1fr] items-baseline gap-4 py-4"
              >
                <span className="font-display text-base text-accent">{t.year}</span>
                <span className="text-sm leading-6 text-foreground/85">{t.event}</span>
              </li>
            ))}
          </ol>
        </section>

        <footer className="mt-20 flex items-center justify-between border-t border-rule pt-6 text-xs text-muted">
          <span className="font-mono uppercase tracking-widest">Antikythera</span>
          <span>Sources: National Archaeological Museum, Athens · Antikythera Research Project</span>
        </footer>
      </article>
    </main>
  );
}
