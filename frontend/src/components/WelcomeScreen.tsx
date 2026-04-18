'use client';

const EXAMPLE_QUESTIONS = [
  {
    icon: 'analytics',
    question: 'What is the expense ratio of HDFC Mid Cap Fund – Direct Growth?',
  },
  {
    icon: 'lock',
    question: 'What is the lock-in period for HDFC ELSS Tax Saver Fund?',
  },
  {
    icon: 'download',
    question: 'How can I download my capital gains statement?',
  },
];

export function WelcomeScreen({
  onExampleClick,
}: {
  onExampleClick: (q: string) => void;
}) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-6 pb-40">
      {/* ── Greeting ───────────────────────────────────────────────── */}
      <div className="max-w-2xl w-full text-center mb-12">
        <h1 className="text-4xl md:text-5xl font-extrabold text-on-surface mb-4 tracking-tight font-headline leading-tight">
          How can I assist<br />your research?
        </h1>
        <p className="text-on-surface-variant font-medium text-base">
          Access factual data, compliance rules, and fund specifics instantly.
        </p>
      </div>

      {/* ── Prompt cards ───────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-4xl w-full">
        {EXAMPLE_QUESTIONS.map(({ icon, question }) => (
          <button
            key={question}
            onClick={() => onExampleClick(question)}
            className="group text-left bg-surface-container-lowest p-6 rounded-xl border border-transparent hover:border-primary/20 hover:shadow-xl transition-all duration-300 flex flex-col justify-between h-48 cursor-pointer"
          >
            <span
              className="material-symbols-outlined text-primary text-[32px]"
              style={{ fontVariationSettings: "'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 24" }}
            >
              {icon}
            </span>
            <p className="text-on-surface font-semibold text-sm leading-relaxed">
              {question}
            </p>
          </button>
        ))}
      </div>
    </div>
  );
}
