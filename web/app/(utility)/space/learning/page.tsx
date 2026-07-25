"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";
import {
  GraduationCap,
  Loader2,
  RotateCcw,
  Trash2,
  CircleCheck,
  CircleDot,
  Circle,
  MessageSquare,
  Package,
  Sparkles,
} from "lucide-react";

import {
  fetchAllProgress,
  fetchMasteryMap,
  deleteProgress,
  redoProgress,
  type ProgressSummary,
  type MasteryMapResult,
  type ObjectiveStatus,
} from "@/lib/learning-api";
import {
  composeAndSeedCognisphere,
  domainFromCognispherePathId,
  fetchCognisphereLearningStatus,
  importAndSeedCognisphere,
  isCognispherePathId,
  masteryChatHref,
  planCognispherePath,
  startCognisphereTutor,
  suggestCognisphereFocus,
  type CognisphereLearningStatus,
} from "@/lib/cognisphere-learning-api";

/**
 * Mastery Path dashboard — the persistent "screen" of the mastery experience.
 *
 * The tutoring itself runs on the chat agent loop (pick "Mastery Path" mode in
 * Chat); this page is the map of where the learner stands. Cognisphere Learning
 * Plugins can seed a ``csphere-{domain}`` path via import-and-seed.
 */
export default function MasteryPathPage() {
  const { i18n } = useTranslation();
  const zh = i18n.language?.toLowerCase().startsWith("zh");
  const tr = useCallback((cn: string, en: string) => (zh ? cn : en), [zh]);
  const router = useRouter();

  const [paths, setPaths] = useState<ProgressSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<MasteryMapResult | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [csphere, setCsphere] = useState<CognisphereLearningStatus | null>(null);
  const [csphereBusy, setCsphereBusy] = useState(false);
  const [csphereError, setCsphereError] = useState<string | null>(null);
  const [csphereNote, setCsphereNote] = useState<string | null>(null);
  const [focusHint, setFocusHint] = useState<string | null>(null);
  const [planHint, setPlanHint] = useState<string | null>(null);
  const [selectedDomains, setSelectedDomains] = useState<string[]>([]);
  const [tutorBusy, setTutorBusy] = useState(false);

  const loadList = useCallback(async () => {
    setLoadingList(true);
    try {
      const result = await fetchAllProgress();
      const withContent = result.summaries
        .filter((s) => s.kp_count > 0)
        .sort((a, b) => b.updated_at - a.updated_at);
      setPaths(withContent);
      setSelected((prev) => prev ?? withContent[0]?.book_id ?? null);
    } catch {
      setPaths([]);
    } finally {
      setLoadingList(false);
    }
  }, []);

  const loadCsphere = useCallback(async () => {
    try {
      const status = await fetchCognisphereLearningStatus();
      setCsphere(status);
      setCsphereError(null);
    } catch (err) {
      setCsphere(null);
      setCsphereError(
        err instanceof Error
          ? err.message
          : tr("无法连接 Cognisphere 插件", "Cognisphere plugins unavailable"),
      );
    }
  }, [tr]);

  useEffect(() => {
    loadList();
    loadCsphere();
  }, [loadList, loadCsphere]);

  useEffect(() => {
    if (!selected) {
      setDetail(null);
      setFocusHint(null);
      setPlanHint(null);
      return;
    }
    let cancelled = false;
    setLoadingDetail(true);
    fetchMasteryMap(selected)
      .then((result) => {
        if (!cancelled) setDetail(result);
      })
      .catch(() => {
        if (!cancelled) setDetail(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingDetail(false);
      });

    const domain = domainFromCognispherePathId(selected);
    if (domain) {
      suggestCognisphereFocus({ domain, pathId: selected })
        .then((focus) => {
          if (cancelled) return;
          const suggestion = focus?.suggestion?.suggestion || focus?.suggestion;
          const slug = focus?.suggestion?.problem_slug;
          const hint = focus?.suggestion?.hint_level;
          if (suggestion || slug) {
            setFocusHint(
              [
                slug ? `slug: ${slug}` : null,
                typeof suggestion === "string" ? `focus: ${suggestion}` : null,
                hint != null ? `hint ${hint}` : null,
              ]
                .filter(Boolean)
                .join(" · "),
            );
          } else {
            setFocusHint(null);
          }
        })
        .catch(() => {
          if (!cancelled) setFocusHint(null);
        });
      planCognispherePath({ domain, pathId: selected })
        .then((plan) => {
          if (cancelled) return;
          const steps = plan?.plan?.steps || plan?.steps || plan?.path;
          const summary =
            plan?.plan?.summary ||
            plan?.summary ||
            (Array.isArray(steps)
              ? steps
                  .slice(0, 3)
                  .map((s: unknown) =>
                    typeof s === "string"
                      ? s
                      : (s as { name?: string; skill_id?: string })?.name ||
                        (s as { skill_id?: string })?.skill_id,
                  )
                  .filter(Boolean)
                  .join(" → ")
              : null);
          setPlanHint(
            typeof summary === "string" && summary
              ? summary
              : plan?.ok
                ? tr("路径计划已就绪", "Skill path ready")
                : null,
          );
        })
        .catch(() => {
          if (!cancelled) setPlanHint(null);
        });
    } else {
      setFocusHint(null);
      setPlanHint(null);
    }

    return () => {
      cancelled = true;
    };
  }, [selected, tr]);

  const handleDelete = useCallback(
    async (pathId: string) => {
      if (
        !window.confirm(
          tr("确定删除这条精通之路？", "Delete this mastery path?"),
        )
      )
        return;
      await deleteProgress(pathId);
      if (selected === pathId) setSelected(null);
      await loadList();
    },
    [selected, loadList, tr],
  );

  const handleRedo = useCallback(
    async (pathId: string) => {
      if (
        !window.confirm(
          tr(
            "重置进度？知识点保留，但掌握度与复习计划清空。",
            "Reset progress? Objectives are kept, but mastery and reviews are cleared.",
          ),
        )
      )
        return;
      await redoProgress(pathId);
      const result = await fetchMasteryMap(pathId);
      setDetail(result);
    },
    [tr],
  );

  const handleImportDomain = useCallback(
    async (domain: string) => {
      setCsphereBusy(true);
      setCsphereError(null);
      setCsphereNote(null);
      try {
        const result = await importAndSeedCognisphere(domain);
        const pathId = result.mastery_path?.path_id;
        if (result.mastery_path?.note) {
          setCsphereNote(result.mastery_path.note);
        }
        await loadList();
        if (pathId) setSelected(pathId);
      } catch (err) {
        setCsphereError(
          err instanceof Error ? err.message : tr("导入失败", "Import failed"),
        );
      } finally {
        setCsphereBusy(false);
      }
    },
    [loadList, tr],
  );

  const toggleDomain = useCallback((domain: string) => {
    setSelectedDomains((prev) =>
      prev.includes(domain)
        ? prev.filter((d) => d !== domain)
        : [...prev, domain],
    );
  }, []);

  const handleComposeAndSeed = useCallback(async () => {
    if (selectedDomains.length === 0) {
      setCsphereError(
        tr("请先勾选至少一个域", "Select at least one domain"),
      );
      return;
    }
    setCsphereBusy(true);
    setCsphereError(null);
    setCsphereNote(null);
    try {
      const result = await composeAndSeedCognisphere({
        domains: selectedDomains,
      });
      const notes = [
        tr(
          `组合完成：成功 ${result.seeded_count}，失败 ${result.failed_count}`,
          `Compose done: ${result.seeded_count} seeded, ${result.failed_count} failed`,
        ),
        ...(result.seeds || [])
          .filter((s) => "mastery_path" in s && s.mastery_path?.note)
          .map((s) =>
            "mastery_path" in s ? String(s.mastery_path?.note) : "",
          )
          .filter(Boolean),
      ];
      setCsphereNote(notes.join(" · "));
      if (result.failed_count > 0 && result.seeded_count === 0) {
        setCsphereError(
          tr("组合导入全部失败", "Compose-and-seed failed for all domains"),
        );
      }
      await loadList();
      const firstPath = result.seeds?.find(
        (s) => "mastery_path" in s && s.mastery_path?.path_id,
      );
      if (firstPath && "mastery_path" in firstPath) {
        setSelected(firstPath.mastery_path!.path_id);
      }
    } catch (err) {
      setCsphereError(
        err instanceof Error
          ? err.message
          : tr("组合导入失败", "Compose-and-seed failed"),
      );
    } finally {
      setCsphereBusy(false);
    }
  }, [selectedDomains, loadList, tr]);

  const handleSocraticPractice = useCallback(async () => {
    const domain = selected ? domainFromCognispherePathId(selected) : null;
    if (!selected || !domain) return;
    setTutorBusy(true);
    try {
      const problemKp = detail?.map.modules
        .flatMap((m) => m.knowledge_points)
        .find((kp) => kp.id.startsWith("prob-") || kp.type === "procedure");
      const practiceSlug = problemKp?.id.startsWith("prob-")
        ? problemKp.id.replace(/^prob-/, "")
        : detail?.next?.knowledge_point_name
            ?.toLowerCase()
            .replace(/\s+/g, "-");
      if (!practiceSlug) {
        setCsphereError(
          tr(
            "当前路径没有可练习的知识点",
            "No practice item available on this path",
          ),
        );
        return;
      }
      const started = await startCognisphereTutor({
        domain,
        slug: practiceSlug,
        hintLevel: 1,
        pathId: selected,
      });
      const href =
        started.continue_in_chat ||
        masteryChatHref(selected, {
          tutorSessionId: started.tutor_session_id,
        });
      router.push(href);
    } catch (err) {
      setCsphereError(
        err instanceof Error
          ? err.message
          : tr("无法启动苏格拉底辅导", "Could not start Socratic tutor"),
      );
    } finally {
      setTutorBusy(false);
    }
  }, [selected, detail, router, tr]);

  return (
    <div className="flex h-full">
      <aside className="w-64 shrink-0 border-r border-[var(--border)] flex flex-col">
        <header className="px-4 py-3 border-b border-[var(--border)]">
          <div className="flex items-center gap-2 text-[var(--foreground)]">
            <GraduationCap className="w-4 h-4" />
            <h1 className="text-sm font-semibold">
              {tr("精通之路", "Mastery Path")}
            </h1>
          </div>
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">
            {tr(
              "掌握式学习：硬门槛 + 间隔复习",
              "Mastery-based learning: hard gate + spaced review",
            )}
          </p>
        </header>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {loadingList ? (
            <div className="flex items-center justify-center py-8 text-[var(--muted-foreground)]">
              <Loader2 className="w-4 h-4 animate-spin" />
            </div>
          ) : paths.length === 0 ? (
            <p className="px-2 py-3 text-xs text-[var(--muted-foreground)] leading-relaxed">
              {tr(
                "还没有精通之路。可从下方 Cognisphere 导入，或去「对话」选择 Mastery Path 模式。",
                "No paths yet. Import from Cognisphere below, or open Chat in Mastery Path mode.",
              )}
            </p>
          ) : (
            paths.map((path) => (
              <button
                key={path.book_id}
                onClick={() => setSelected(path.book_id)}
                className={`w-full text-left px-3 py-2 rounded-md transition-colors cursor-pointer ${
                  selected === path.book_id
                    ? "bg-[var(--primary)]/10 ring-1 ring-[var(--primary)]/30"
                    : "hover:bg-[var(--accent)]"
                }`}
              >
                <div className="truncate text-sm text-[var(--foreground)]">
                  {path.name}
                </div>
                <div className="mt-0.5 text-xs text-[var(--muted-foreground)]">
                  {isCognispherePathId(path.book_id) && (
                    <span className="mr-1 text-[var(--primary)]">CS · </span>
                  )}
                  {path.kp_count} {tr("个知识点", "objectives")} ·{" "}
                  {path.avg_mastery_pct}%
                </div>
              </button>
            ))
          )}
        </div>

        <div className="border-t border-[var(--border)] p-2 space-y-2">
          <div className="flex items-center gap-1.5 px-1 text-xs font-medium text-[var(--foreground)]">
            <Package className="w-3.5 h-3.5" />
            {tr("Cognisphere 插件", "Cognisphere plugins")}
          </div>
          {csphereError && (
            <p className="px-1 text-[10px] leading-relaxed text-red-500/90">
              {csphereError}
            </p>
          )}
          {csphereNote && (
            <p className="px-1 text-[10px] leading-relaxed text-yellow-600">
              {csphereNote}
            </p>
          )}
          {csphere && !csphere.ok && (
            <p className="px-1 text-[10px] leading-relaxed text-[var(--muted-foreground)]">
              {tr(
                "未找到插件根目录。请设置 COGNISPHERE_LEARNING_PLUGINS_ROOT。",
                "Plugins root missing. Set COGNISPHERE_LEARNING_PLUGINS_ROOT.",
              )}
            </p>
          )}
          {csphere?.gates?.trusted_context && (
            <p className="px-1 text-[10px] leading-relaxed text-[var(--muted-foreground)]">
              {tr("可信上下文", "Trusted context")}:{" "}
              {csphere.gates.trusted_context.kit_configured
                ? tr("在线 kit 已配置", "live kit configured")
                : tr("仅离线导入", "offline import only")}
              {csphere.gates.trusted_context.mode
                ? ` · ${csphere.gates.trusted_context.mode}`
                : ""}
              {!csphere.gates.trusted_context.kit_configured &&
              csphere.gates.trusted_context.blocker?.code
                ? ` · ${csphere.gates.trusted_context.blocker.code}`
                : ""}
            </p>
          )}
          <div className="space-y-1">
            {(csphere?.plugins || []).map((plugin) => (
              <div
                key={plugin.domain}
                className="flex items-center gap-1.5 px-1 py-1 rounded-md text-xs border border-[var(--border)]"
              >
                <label className="flex items-center gap-1.5 flex-1 min-w-0 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedDomains.includes(plugin.domain)}
                    disabled={!plugin.valid || csphereBusy}
                    onChange={() => toggleDomain(plugin.domain)}
                    className="shrink-0"
                  />
                  <span className="truncate text-[var(--foreground)]">
                    {plugin.domain}
                  </span>
                </label>
                <button
                  type="button"
                  disabled={csphereBusy || !plugin.valid}
                  onClick={() => handleImportDomain(plugin.domain)}
                  className="shrink-0 text-[var(--muted-foreground)] hover:text-[var(--primary)] disabled:opacity-50 cursor-pointer px-1"
                >
                  {csphereBusy ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    tr("导入", "Import")
                  )}
                </button>
              </div>
            ))}
            {!csphere?.plugins?.length && !csphereError && (
              <p className="px-1 text-[10px] text-[var(--muted-foreground)]">
                {tr("暂无可用域", "No domains available")}
              </p>
            )}
          </div>
          <button
            type="button"
            disabled={csphereBusy || selectedDomains.length === 0}
            onClick={handleComposeAndSeed}
            className="w-full flex items-center justify-center gap-1.5 px-2 py-1.5 text-xs rounded-md border border-[var(--primary)]/40 text-[var(--primary)] hover:bg-[var(--primary)]/10 disabled:opacity-50 cursor-pointer"
          >
            {csphereBusy ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <Package className="w-3 h-3" />
            )}
            {tr(
              `组合并导入 (${selectedDomains.length})`,
              `Compose & seed (${selectedDomains.length})`,
            )}
          </button>
        </div>

        <footer className="p-2 border-t border-[var(--border)]">
          <button
            onClick={() =>
              router.push(
                selected
                  ? masteryChatHref(selected)
                  : "/home?capability=mastery_path",
              )
            }
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-sm rounded-md bg-[var(--primary)] text-[var(--primary-foreground)] hover:opacity-90 transition-opacity cursor-pointer"
          >
            <MessageSquare className="w-3.5 h-3.5" />
            {tr("在对话中继续（Mastery）", "Continue in Chat (Mastery)")}
          </button>
        </footer>
      </aside>

      <section className="flex-1 overflow-y-auto">
        {loadingDetail ? (
          <div className="flex items-center justify-center h-full text-[var(--muted-foreground)]">
            <Loader2 className="w-5 h-5 animate-spin" />
          </div>
        ) : !detail ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-6 text-[var(--muted-foreground)]">
            <GraduationCap className="w-10 h-10 mb-3 opacity-40" />
            <p className="text-sm max-w-sm leading-relaxed">
              {tr(
                "选择一条精通之路查看进度地图，从左侧导入 Cognisphere 插件，或在「对话」里用 Mastery Path 模式开始。",
                "Select a path to see its progress map, import a Cognisphere pack on the left, or start one in Chat with Mastery Path mode.",
              )}
            </p>
          </div>
        ) : (
          <MapView
            result={detail}
            zh={!!zh}
            tr={tr}
            cognisphere={selected ? isCognispherePathId(selected) : false}
            focusHint={focusHint}
            planHint={planHint}
            tutorBusy={tutorBusy}
            onContinue={() =>
              selected && router.push(masteryChatHref(selected))
            }
            onSocratic={handleSocraticPractice}
            onRedo={() => selected && handleRedo(selected)}
            onDelete={() => selected && handleDelete(selected)}
          />
        )}
      </section>
    </div>
  );
}

const STATUS_META: Record<
  ObjectiveStatus,
  { cn: string; en: string; className: string }
> = {
  mastered: { cn: "已掌握", en: "Mastered", className: "text-green-500" },
  learning: { cn: "学习中", en: "Learning", className: "text-yellow-500" },
  new: {
    cn: "未开始",
    en: "Not started",
    className: "text-[var(--muted-foreground)]",
  },
};

const ACTION_LABEL: Record<string, { cn: string; en: string }> = {
  probe: { cn: "先探查是否已掌握", en: "Probe — test out first" },
  practice: { cn: "练习直到达标", en: "Practice until the gate clears" },
  assess: { cn: "用自己的话解释", en: "Explain it in your own words" },
  review: { cn: "到期复习", en: "Due for review" },
  answer_pending: {
    cn: "有待回答的问题",
    en: "A question is awaiting your answer",
  },
  complete: { cn: "已全部掌握 🎉", en: "All mastered 🎉" },
};

function StatusIcon({ status }: { status: ObjectiveStatus }) {
  const cls = `w-3 h-3 shrink-0 ${STATUS_META[status].className}`;
  if (status === "mastered") return <CircleCheck className={cls} />;
  if (status === "learning") return <CircleDot className={cls} />;
  return <Circle className={cls} />;
}

function MapView({
  result,
  zh,
  tr,
  cognisphere,
  focusHint,
  planHint,
  tutorBusy,
  onContinue,
  onSocratic,
  onRedo,
  onDelete,
}: {
  result: MasteryMapResult;
  zh: boolean;
  tr: (cn: string, en: string) => string;
  cognisphere: boolean;
  focusHint: string | null;
  planHint: string | null;
  tutorBusy: boolean;
  onContinue: () => void;
  onSocratic: () => void;
  onRedo: () => void;
  onDelete: () => void;
}) {
  const { map, next } = result;
  const pct = map.counts.total
    ? Math.round((map.counts.mastered / map.counts.total) * 100)
    : 0;
  const action = ACTION_LABEL[next.action] ?? {
    cn: next.reason,
    en: next.reason,
  };

  return (
    <div className="max-w-2xl mx-auto px-6 py-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
            <span>
              {map.counts.mastered}/{map.counts.total}{" "}
              {tr("已掌握", "mastered")}
            </span>
            {map.due_reviews > 0 && (
              <span className="text-yellow-600">
                · {map.due_reviews} {tr("项待复习", "due for review")}
              </span>
            )}
            {cognisphere && (
              <span className="text-[var(--primary)]">· Cognisphere</span>
            )}
          </div>
          <div className="mt-1.5 h-1.5 w-full rounded-full bg-[var(--accent)] overflow-hidden">
            <div
              className="h-full bg-green-500 transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={onRedo}
            title={tr("重置进度", "Reset progress")}
            className="p-1.5 rounded-md text-[var(--muted-foreground)] hover:bg-[var(--accent)] cursor-pointer"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
          <button
            onClick={onDelete}
            title={tr("删除", "Delete")}
            className="p-1.5 rounded-md text-[var(--muted-foreground)] hover:bg-red-500/10 hover:text-red-500 cursor-pointer"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <button
        onClick={onContinue}
        className="mt-4 w-full text-left rounded-lg border border-[var(--border)] hover:border-[var(--primary)]/40 hover:bg-[var(--accent)] p-3 transition-colors cursor-pointer"
      >
        <div className="text-xs text-[var(--muted-foreground)]">
          {tr("接下来", "Next")}
        </div>
        <div className="mt-0.5 text-sm font-medium text-[var(--foreground)]">
          {next.action === "complete"
            ? tr(action.cn, action.en)
            : `${next.knowledge_point_name} — ${tr(action.cn, action.en)}`}
        </div>
        <div className="mt-1 text-xs text-[var(--primary)]">
          {tr("在对话中继续辅导 →", "Continue tutoring in Chat →")}
        </div>
      </button>

      {cognisphere && (
        <div className="mt-3 rounded-lg border border-[var(--border)] p-3 space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-medium text-[var(--foreground)]">
            <Sparkles className="w-3.5 h-3.5" />
            {tr("Cognisphere 苏格拉底练习", "Cognisphere Socratic practice")}
          </div>
          {focusHint && (
            <p className="text-[11px] text-[var(--muted-foreground)]">
              {tr("推荐焦点", "Suggested focus")}: {focusHint}
            </p>
          )}
          {planHint && (
            <p className="text-[11px] text-[var(--muted-foreground)]">
              {tr("技能路径", "Skill path")}: {planHint}
            </p>
          )}
          <button
            onClick={onSocratic}
            disabled={tutorBusy}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-sm rounded-md border border-[var(--primary)]/40 text-[var(--primary)] hover:bg-[var(--primary)]/10 disabled:opacity-50 cursor-pointer"
          >
            {tutorBusy ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Sparkles className="w-3.5 h-3.5" />
            )}
            {tr(
              "启动离线苏格拉底会话并进入对话",
              "Start offline Socratic session & open Chat",
            )}
          </button>
        </div>
      )}

      <div className="mt-5 space-y-4">
        {map.modules.map((module) => (
          <div key={module.id}>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-[var(--foreground)]">
                {module.name}
              </h3>
              <span className="text-xs text-[var(--muted-foreground)]">
                {module.mastered}/{module.total}
              </span>
            </div>
            <div className="mt-1.5 space-y-1">
              {module.knowledge_points.map((kp) => (
                <div
                  key={kp.id}
                  className="flex items-center gap-2 px-2 py-1 rounded-md text-sm"
                >
                  <StatusIcon status={kp.status} />
                  <span className="flex-1 truncate text-[var(--foreground)]">
                    {kp.name}
                  </span>
                  <span className="text-[10px] uppercase tracking-wide text-[var(--muted-foreground)]">
                    {kp.type}
                  </span>
                  <span
                    className={`text-xs ${STATUS_META[kp.status].className}`}
                  >
                    {zh ? STATUS_META[kp.status].cn : STATUS_META[kp.status].en}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
