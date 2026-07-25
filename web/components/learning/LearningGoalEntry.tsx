"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Sparkles } from "lucide-react";
import {
  learningSpaceGoalHref,
  masteryChatHref,
  recommendCognisphereFromGoal,
} from "@/lib/cognisphere-learning-api";

/**
 * Compact NL learning-goal capture for Chat home / Learning Space.
 * Recommend plugins, then continue to Learning Space compose/seed or one-click seed.
 */
export default function LearningGoalEntry({
  tr,
  compact = false,
  initialGoal = "",
  onSeeded,
}: {
  tr: (cn: string, en: string) => string;
  compact?: boolean;
  initialGoal?: string;
  onSeeded?: (pathId: string | null) => void;
}) {
  const router = useRouter();
  const [goal, setGoal] = useState(initialGoal);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recommended, setRecommended] = useState<string[]>([]);

  const handleRecommend = useCallback(async () => {
    const text = goal.trim();
    if (!text) {
      setError(tr("请先输入学习目标", "Enter a learning goal first"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await recommendCognisphereFromGoal({
        goal: text,
        composeAndSeed: false,
      });
      const domains = result.recommended_domains || [];
      setRecommended(domains);
      if (!domains.length) {
        setError(
          tr(
            "没有匹配的插件，请调整目标或安装域插件",
            "No plugins matched — adjust the goal or install domain plugins",
          ),
        );
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : tr("推荐失败", "Recommend failed"),
      );
      setRecommended([]);
    } finally {
      setBusy(false);
    }
  }, [goal, tr]);

  const handleOpenLearningSpace = useCallback(() => {
    const text = goal.trim();
    if (!text) {
      setError(tr("请先输入学习目标", "Enter a learning goal first"));
      return;
    }
    router.push(
      learningSpaceGoalHref(text, {
        domains: recommended.length ? recommended : undefined,
      }),
    );
  }, [goal, recommended, router, tr]);

  const handleComposeAndSeed = useCallback(async () => {
    const text = goal.trim();
    if (!text) {
      setError(tr("请先输入学习目标", "Enter a learning goal first"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await recommendCognisphereFromGoal({
        goal: text,
        composeAndSeed: true,
      });
      const domains = result.recommended_domains || [];
      setRecommended(domains);
      let firstPath: string | null = null;
      for (const seed of result.compose_seed?.seeds || []) {
        if (
          seed &&
          typeof seed === "object" &&
          "mastery_path" in seed &&
          seed.mastery_path?.path_id
        ) {
          firstPath = seed.mastery_path.path_id;
          break;
        }
      }
      onSeeded?.(firstPath);
      if (result.continue_in_chat) {
        router.push(result.continue_in_chat);
        return;
      }
      if (firstPath) {
        router.push(masteryChatHref(firstPath));
        return;
      }
      router.push(
        learningSpaceGoalHref(text, {
          domains: domains.length ? domains : undefined,
        }),
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : tr("组合导入失败", "Compose & seed failed"),
      );
    } finally {
      setBusy(false);
    }
  }, [goal, onSeeded, router, tr]);

  return (
    <div
      className={`w-full rounded-lg border border-[var(--border)] bg-[var(--background)]/60 ${
        compact ? "p-2.5 space-y-1.5" : "p-3 space-y-2"
      }`}
    >
      <div className="flex items-center gap-1.5 text-xs font-medium text-[var(--foreground)]">
        <Sparkles className={`shrink-0 ${compact ? "w-3.5 h-3.5" : "w-4 h-4"}`} />
        {tr("用目标开始学习", "Start from a learning goal")}
      </div>
      <textarea
        value={goal}
        onChange={(e) => setGoal(e.target.value)}
        rows={compact ? 2 : 2}
        disabled={busy}
        placeholder={tr(
          "例如：我想系统练习面试算法与微积分…",
          "e.g. I want a structured path for interview algorithms and calculus…",
        )}
        className="w-full resize-none rounded-md border border-[var(--border)] bg-transparent px-2.5 py-2 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)]"
      />
      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          disabled={busy || !goal.trim()}
          onClick={handleRecommend}
          className="px-2.5 py-1.5 text-xs rounded-md border border-[var(--border)] hover:bg-[var(--accent)] disabled:opacity-50 cursor-pointer"
        >
          {busy ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin inline" />
          ) : (
            tr("推荐插件", "Recommend")
          )}
        </button>
        <button
          type="button"
          disabled={busy || !goal.trim()}
          onClick={handleOpenLearningSpace}
          className="px-2.5 py-1.5 text-xs rounded-md border border-[var(--border)] hover:bg-[var(--accent)] disabled:opacity-50 cursor-pointer"
        >
          {tr("去学习空间继续", "Continue in Learning Space")}
        </button>
        <button
          type="button"
          disabled={busy || !goal.trim()}
          onClick={handleComposeAndSeed}
          className="px-2.5 py-1.5 text-xs rounded-md border border-[var(--primary)]/40 text-[var(--primary)] hover:bg-[var(--primary)]/10 disabled:opacity-50 cursor-pointer"
        >
          {tr("一键组合导入并进入对话", "Compose, seed & open Chat")}
        </button>
      </div>
      {recommended.length > 0 && (
        <p className="text-[11px] text-[var(--muted-foreground)]">
          {tr("已推荐", "Recommended")}: {recommended.join(", ")}
        </p>
      )}
      {error && (
        <p className="text-[11px] leading-relaxed text-red-500/90">{error}</p>
      )}
    </div>
  );
}
