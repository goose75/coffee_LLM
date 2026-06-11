"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface QuizAnswers {
  preference: string | null;
  brewMethod: string | null;
  budget: string | null;
}

interface QuickQuizModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function QuickQuizModal({ isOpen, onClose }: QuickQuizModalProps) {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<QuizAnswers>({
    preference: null,
    brewMethod: null,
    budget: null,
  });

  const handleAnswer = (field: keyof QuizAnswers, value: string) => {
    setAnswers({ ...answers, [field]: value });
    if (step < 2) {
      setStep(step + 1);
    }
  };

  const handleSubmit = () => {
    const params = new URLSearchParams();

    // Map quiz answers to query parameters
    if (answers.preference === "light") params.set("roast", "light");
    else if (answers.preference === "medium") params.set("roast", "medium");
    else if (answers.preference === "dark") params.set("roast", "dark");
    else if (answers.preference === "decaf") params.set("decaf", "true");

    // Map brew method to filter
    if (answers.brewMethod === "espresso") params.set("brew", "espresso");
    else if (answers.brewMethod === "filter") params.set("brew", "filter");
    else if (answers.brewMethod === "other") params.set("brew", "other");

    // Map budget to price range
    if (answers.budget === "budget") params.set("price_max", "12");
    else if (answers.budget === "mid") params.set("price_max", "18");
    else if (answers.budget === "premium") params.set("price_min", "18");

    onClose();
    router.push(`/coffees?${params.toString()}`);
  };

  const isComplete = answers.preference && answers.brewMethod && answers.budget;

  if (!isOpen) return null;

  return (
    <div className="quiz-modal-overlay" onClick={onClose}>
      <div className="quiz-modal" onClick={(e) => e.stopPropagation()}>
        <button className="quiz-close" onClick={onClose} aria-label="Close">×</button>

        <div className="quiz-header">
          <h2 className="quiz-title">Find Your Perfect Coffee</h2>
          <p className="quiz-subtitle">Answer 3 quick questions</p>
          <div className="quiz-progress">
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${((step + 1) / 3) * 100}%` }} />
            </div>
            <span className="progress-text">
              Question {step + 1} of 3
            </span>
          </div>
        </div>

        <div className="quiz-content">
          {/* Step 0: Preference */}
          {step === 0 && (
            <div className="quiz-step">
              <h3 className="quiz-question">How do you like your coffee?</h3>
              <div className="quiz-options">
                {[
                  { value: "light", label: "Light & fruity" },
                  { value: "medium", label: "Medium & balanced" },
                  { value: "dark", label: "Dark & bold" },
                  { value: "decaf", label: "Decaf" },
                ].map((opt) => (
                  <button
                    key={opt.value}
                    className={`quiz-option ${answers.preference === opt.value ? "active" : ""}`}
                    onClick={() => handleAnswer("preference", opt.value)}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Step 1: Brew Method */}
          {step === 1 && (
            <div className="quiz-step">
              <h3 className="quiz-question">How do you brew?</h3>
              <div className="quiz-options">
                {[
                  { value: "espresso", label: "Espresso" },
                  { value: "filter", label: "Filter / Pour Over" },
                  { value: "other", label: "Other / All methods" },
                ].map((opt) => (
                  <button
                    key={opt.value}
                    className={`quiz-option ${answers.brewMethod === opt.value ? "active" : ""}`}
                    onClick={() => handleAnswer("brewMethod", opt.value)}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Step 2: Budget */}
          {step === 2 && (
            <div className="quiz-step">
              <h3 className="quiz-question">What's your budget?</h3>
              <div className="quiz-options">
                {[
                  { value: "budget", label: "Under £12" },
                  { value: "mid", label: "£12-18" },
                  { value: "premium", label: "£18+" },
                ].map((opt) => (
                  <button
                    key={opt.value}
                    className={`quiz-option ${answers.budget === opt.value ? "active" : ""}`}
                    onClick={() => handleAnswer("budget", opt.value)}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="quiz-footer">
          <button
            className="quiz-button quiz-button-secondary"
            onClick={() => step > 0 ? setStep(step - 1) : onClose()}
          >
            {step > 0 ? "← Back" : "Cancel"}
          </button>
          {step < 2 ? (
            <button
              className="quiz-button quiz-button-primary"
              onClick={() => setStep(step + 1)}
              disabled={!answers.preference && step === 0 || !answers.brewMethod && step === 1}
            >
              Next →
            </button>
          ) : (
            <button
              className="quiz-button quiz-button-primary"
              onClick={handleSubmit}
              disabled={!isComplete}
            >
              Show Results
            </button>
          )}
        </div>
      </div>

      <style jsx>{`
        .quiz-modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          padding: 20px;
        }

        .quiz-modal {
          background: var(--surface);
          border-radius: 12px;
          max-width: 480px;
          width: 100%;
          position: relative;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
          animation: slideUp 0.3s ease-out;
        }

        @keyframes slideUp {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .quiz-close {
          position: absolute;
          top: 16px;
          right: 16px;
          width: 32px;
          height: 32px;
          border: none;
          background: none;
          font-size: 28px;
          cursor: pointer;
          color: var(--text-faint);
          padding: 0;
          transition: color 0.2s;
        }

        .quiz-close:hover {
          color: var(--text);
        }

        .quiz-header {
          padding: 32px 24px 24px;
          border-bottom: 1px solid var(--border-light);
        }

        .quiz-title {
          margin: 0 0 4px 0;
          font-size: 24px;
          font-weight: 500;
          color: var(--text);
          font-family: var(--font-display);
        }

        .quiz-subtitle {
          margin: 0 0 16px 0;
          font-size: 14px;
          color: var(--text-muted);
        }

        .quiz-progress {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .progress-bar {
          height: 4px;
          background: var(--border-light);
          border-radius: 2px;
          overflow: hidden;
        }

        .progress-fill {
          height: 100%;
          background: var(--accent);
          transition: width 0.3s ease;
        }

        .progress-text {
          font-size: 12px;
          color: var(--text-faint);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .quiz-content {
          padding: 32px 24px;
          min-height: 240px;
        }

        .quiz-step {
          animation: fadeIn 0.2s ease-out;
        }

        @keyframes fadeIn {
          from {
            opacity: 0;
          }
          to {
            opacity: 1;
          }
        }

        .quiz-question {
          margin: 0 0 20px 0;
          font-size: 18px;
          font-weight: 500;
          color: var(--text);
        }

        .quiz-options {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .quiz-option {
          padding: 12px 16px;
          border: 1.5px solid var(--border-light);
          border-radius: 8px;
          background: var(--bg);
          color: var(--text);
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
          text-align: left;
        }

        .quiz-option:hover {
          border-color: var(--accent);
          background: var(--surface);
        }

        .quiz-option.active {
          border-color: var(--accent);
          background: rgba(181, 136, 42, 0.1);
          color: var(--accent);
        }

        .quiz-footer {
          display: flex;
          gap: 12px;
          padding: 20px 24px;
          border-top: 1px solid var(--border-light);
        }

        .quiz-button {
          flex: 1;
          padding: 12px 16px;
          border: none;
          border-radius: 8px;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
        }

        .quiz-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .quiz-button-secondary {
          background: var(--surface);
          color: var(--text);
          border: 1px solid var(--border-light);
        }

        .quiz-button-secondary:hover:not(:disabled) {
          background: var(--bg);
        }

        .quiz-button-primary {
          background: var(--accent);
          color: white;
        }

        .quiz-button-primary:hover:not(:disabled) {
          opacity: 0.9;
        }

        @media (max-width: 480px) {
          .quiz-modal {
            max-width: 100%;
            border-radius: 8px;
          }

          .quiz-header {
            padding: 24px 16px 16px;
          }

          .quiz-content {
            padding: 24px 16px;
          }

          .quiz-footer {
            padding: 16px;
          }
        }
      `}</style>
    </div>
  );
}
