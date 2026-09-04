"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslation } from "react-i18next";
import {
  GraduationCap,
  Loader2,
  RotateCcw,
  Trash2,
  Undo2,
  CircleCheck,
  CircleDot,
  Circle,
  Cpu,
  MessageSquare,
  Package,
  Sparkles,
} from "lucide-react";

import {
  fetchAllProgress,
  fetchMasteryMap,
  deleteProgress,
  listProgressBackups,
  redoProgress,
  restoreProgress,
  type ProgressSummary,
  type MasteryMapResult,
  type ObjectiveStatus,
} from "@/lib/learning-api";
import {
  composeAndSeedCognisphere,
  domainFromCognispherePathId,
  fetchAbilityRadar,
  fetchAwsTwinMasteryStatus,
  fetchCognisphereLearningStatus,
  importAndSeedCognisphere,
  isCognispherePathId,
  masteryChatHref,
  planCognispherePath,
  recommendCognisphereFromGoal,
  runAwsTwinMastery,
  runCognisphereHandshake,
  runLearningTwinFlow,
  startCognisphereTutor,
  suggestCognisphereFocus,
  type AbilityRadarResult,
  type AwsTwinMasteryGate,
  type AwsTwinMasteryResult,
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
  return (
    <Suspense
      fallback={
        <div className="flex h-full items-center justify-center text-[var(--muted-foreground)]">
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
      }
    >
      <MasteryPathPageInner />
    </Suspense>
  );
}

function MasteryPathPageInner() {
  const { i18n } = useTranslation();
  const zh = i18n.language?.toLowerCase().startsWith("zh");
  const tr = useCallback((cn: string, en: string) => (zh ? cn : en), [zh]);
  const router = useRouter();
  const searchParams = useSearchParams();
  const goalFromUrl = (searchParams.get("goal") || "").trim();
  const panelFromUrl = (searchParams.get("panel") || "").trim().toLowerCase();
  const domainsFromUrl = (searchParams.get("domains") || "")
    .split(",")
    .map((d) => d.trim())
    .filter(Boolean);

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
  const [goalText, setGoalText] = useState(goalFromUrl);
  const [recommendedDomains, setRecommendedDomains] = useState<string[]>([]);
  const [tutorBusy, setTutorBusy] = useState(false);
  const [radar, setRadar] = useState<AbilityRadarResult | null>(null);
  const [urlGoalApplied, setUrlGoalApplied] = useState(false);
  const [awsTwinBusy, setAwsTwinBusy] = useState(false);
  const [aiInfraBusy, setAiInfraBusy] = useState(false);
  const [awsTwinResult, setAwsTwinResult] = useState<AwsTwinMasteryResult | null>(
    null,
  );
  /** Main pane: mastery map vs AWS Digital Twin practice results. */
  const [mainPanel, setMainPanel] = useState<"map" | "aws-twin">(
    panelFromUrl === "aws-twin" ? "aws-twin" : "map",
  );

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

  // Deep-link from Chat: ?goal=…&domains=a,b pre-fills goal / selection.
  useEffect(() => {
    if (urlGoalApplied) return;
    if (goalFromUrl) {
      setGoalText(goalFromUrl);
    }
    if (domainsFromUrl.length) {
      setSelectedDomains(domainsFromUrl);
      setRecommendedDomains(domainsFromUrl);
    }
    if (goalFromUrl || domainsFromUrl.length) {
      setUrlGoalApplied(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- apply URL once per landing
  }, [goalFromUrl, searchParams, urlGoalApplied]);

  useEffect(() => {
    if (!selected) {
      setDetail(null);
      setFocusHint(null);
      setPlanHint(null);
      setRadar(null);
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

    fetchAbilityRadar({ pathId: selected, includeSkillGraph: true })
      .then((result) => {
        if (!cancelled) setRadar(result);
      })
      .catch(() => {
        if (!cancelled) setRadar(null);
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
            "从头开始这条精通之路？系统会先保存当前进度备份，可稍后恢复。",
            "Start this mastery path from the beginning? Tutor will save a backup first so you can restore it later.",
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

  const handleRestore = useCallback(
    async (pathId: string) => {
      const backups = await listProgressBackups(pathId);
      if (!backups.backups.length) {
        window.alert(
          tr("还没有可恢复的进度备份。", "No restorable progress backup yet."),
        );
        return;
      }
      if (
        !window.confirm(
          tr(
            "恢复最近一次备份？当前进度会被备份内容替换。",
            "Restore the latest backup? Current progress will be replaced.",
          ),
        )
      )
        return;
      await restoreProgress(pathId);
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

  const awsTwinGate = csphere?.gates?.aws_twin_mastery;
  const awsLearningDomain =
    awsTwinGate?.learning_domain || "aws_certification";
  const awsMasteryPathId =
    awsTwinGate?.mastery_path_id || `csphere-${awsLearningDomain}`;
  const aiInfraLearningDomain = "ai_infra";
  const aiInfraMasteryPathId = `csphere-${aiInfraLearningDomain}`;

  const twinModeLabel = useCallback(
    (mode?: string | null) => {
      const m = String(mode || "").toLowerCase();
      if (!m || m.includes("fixture") || m.includes("stub") || m === "offline") {
        return tr("本地模拟（无需真实 AWS）", "Local simulation (no live AWS)");
      }
      if (m.includes("live")) {
        return tr("在线模式", "Live mode");
      }
      return mode || tr("本地模拟", "Local simulation");
    },
    [tr],
  );

  const openAwsTwinPanel = useCallback(() => {
    setMainPanel("aws-twin");
    setCsphereError(null);
  }, []);

  const handleRunAwsTwinMastery = useCallback(async () => {
    setAwsTwinBusy(true);
    setCsphereError(null);
    setCsphereNote(null);
    setMainPanel("aws-twin");
    try {
      // Prefer status gate when already known; refresh if missing.
      if (!awsTwinGate?.ok) {
        const status = await fetchAwsTwinMasteryStatus();
        if (!status.ok) {
          throw new Error(
            status.error ||
              tr(
                "AWS Digital Twin Mastery 不可用（需 COGNISPHERE_LEARNING_PLUGINS_ROOT）",
                "AWS Digital Twin Mastery unavailable (needs COGNISPHERE_LEARNING_PLUGINS_ROOT)",
              ),
          );
        }
      }
      const result = await runAwsTwinMastery();
      setAwsTwinResult(result);
      if (result.ok) {
        setCsphereNote(
          tr(
            `离线练习已完成（${twinModeLabel(result.runtime_mode)}）。右侧已显示步骤结果，可进入 Mastery 对话继续。`,
            `Offline practice complete (${twinModeLabel(result.runtime_mode)}). Step results are on the right; continue in Mastery chat when ready.`,
          ),
        );
      } else {
        setCsphereError(
          result.error ||
            (result.issues || []).join("; ") ||
            tr("AWS twin mastery 未完成", "AWS twin mastery did not complete"),
        );
      }
    } catch (err) {
      setCsphereError(
        err instanceof Error
          ? err.message
          : tr("无法运行 AWS twin mastery", "Could not run AWS twin mastery"),
      );
    } finally {
      setAwsTwinBusy(false);
    }
  }, [awsTwinGate?.ok, tr, twinModeLabel]);

  const handleContinueAwsMasteryPath = useCallback(async () => {
    setAwsTwinBusy(true);
    setCsphereError(null);
    try {
      const existing = paths.find((p) => p.book_id === awsMasteryPathId);
      if (!existing) {
        const seeded = await importAndSeedCognisphere(awsLearningDomain);
        const pathId = seeded.mastery_path?.path_id || awsMasteryPathId;
        await loadList();
        setSelected(pathId);
        router.push(masteryChatHref(pathId, { autoStart: "next" }));
        return;
      }
      setSelected(awsMasteryPathId);
      router.push(
        awsTwinGate?.continue_in_chat ||
          masteryChatHref(awsMasteryPathId, { autoStart: "next" }),
      );
    } catch (err) {
      setCsphereError(
        err instanceof Error
          ? err.message
          : tr(
              "无法打开 AWS Mastery Path",
              "Could not open AWS Mastery Path",
            ),
      );
    } finally {
      setAwsTwinBusy(false);
    }
  }, [
    awsLearningDomain,
    awsMasteryPathId,
    awsTwinGate?.continue_in_chat,
    loadList,
    paths,
    router,
    tr,
  ]);

  const handleContinueAiInfraMasteryPath = useCallback(async () => {
    setAiInfraBusy(true);
    setCsphereError(null);
    setCsphereNote(null);
    try {
      const existing = paths.find((p) => p.book_id === aiInfraMasteryPathId);
      if (!existing) {
        const seeded = await importAndSeedCognisphere(aiInfraLearningDomain);
        const pathId = seeded.mastery_path?.path_id || aiInfraMasteryPathId;
        await loadList();
        setSelected(pathId);
        router.push(masteryChatHref(pathId, { autoStart: "next" }));
        return;
      }
      setSelected(aiInfraMasteryPathId);
      router.push(masteryChatHref(aiInfraMasteryPathId, { autoStart: "next" }));
    } catch (err) {
      setCsphereError(
        err instanceof Error
          ? err.message
          : tr(
              "无法打开 AI Infra Mastery Path",
              "Could not open AI Infra Mastery Path",
            ),
      );
    } finally {
      setAiInfraBusy(false);
    }
  }, [aiInfraMasteryPathId, loadList, paths, router, tr]);

  const handleAwsLearningTwinHandshake = useCallback(async () => {
    setAwsTwinBusy(true);
    setCsphereError(null);
    setCsphereNote(null);
    try {
      const handshake = await runCognisphereHandshake({
        domain: awsLearningDomain,
        goal: goalText.trim() || undefined,
      });
      if (!handshake.ok) {
        throw new Error(
          handshake.error ||
            (handshake.issues || []).join("; ") ||
            tr("Handshake 未通过", "Handshake did not pass"),
        );
      }
      const flow = await runLearningTwinFlow({
        learningDomain: awsLearningDomain,
        goal: goalText.trim() || undefined,
        compositionIntent: "learn_then_practice",
      });
      const summaryOk =
        flow.ok !== false &&
        (flow.summary == null || flow.summary.ok !== false);
      if (!summaryOk) {
        throw new Error(
          flow.error ||
            (flow.issues || []).join("; ") ||
            tr("Learning→Twin 流程未通过", "Learning→Twin flow did not pass"),
        );
      }
      setCsphereNote(
        tr(
          `Handshake + Learning→Twin 完成（intent=learn_then_practice）。可继续跑离线 twin 练习或进入 Mastery 对话。`,
          `Handshake + Learning→Twin complete (intent=learn_then_practice). Run offline twin practice or open Mastery chat.`,
        ),
      );
    } catch (err) {
      setCsphereError(
        err instanceof Error
          ? err.message
          : tr("Handshake 失败", "Handshake failed"),
      );
    } finally {
      setAwsTwinBusy(false);
    }
  }, [awsLearningDomain, goalText, tr]);

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
        tr("请先选择至少一门课程", "Select at least one course"),
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
          `已添加 ${result.seeded_count} 门课程，${result.failed_count} 门未完成`,
          `Added ${result.seeded_count} courses; ${result.failed_count} not completed`,
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
          tr("所选课程暂时无法添加", "Selected courses could not be added"),
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
          : tr("添加课程失败", "Could not add courses"),
      );
    } finally {
      setCsphereBusy(false);
    }
  }, [selectedDomains, loadList, tr]);

  const handleImportAvailableDomains = useCallback(async () => {
    const domains = (csphere?.plugins || [])
      .filter(
        (plugin) =>
          plugin.valid &&
          plugin.kind !== "twin" &&
          !plugin.domain.endsWith("_twin"),
      )
      .map((plugin) => plugin.domain);
    if (domains.length === 0) {
      setCsphereError(
        tr("暂时没有可添加的课程", "No courses are available to add"),
      );
      return;
    }
    setCsphereBusy(true);
    setCsphereError(null);
    setCsphereNote(null);
    try {
      const result = await composeAndSeedCognisphere({ domains });
      setCsphereNote(
        tr(
          `已添加 ${result.seeded_count} 门课程，${result.failed_count} 门未完成`,
          `Added ${result.seeded_count} courses; ${result.failed_count} not completed`,
        ),
      );
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
          : tr("添加全部课程失败", "Could not add all courses"),
      );
    } finally {
      setCsphereBusy(false);
    }
  }, [csphere?.plugins, loadList, tr]);

  const handleRecommendGoal = useCallback(async () => {
    const goal = goalText.trim();
    if (!goal) {
      setCsphereError(
        tr("请先输入学习目标", "Enter a learning goal first"),
      );
      return;
    }
    setCsphereBusy(true);
    setCsphereError(null);
    setCsphereNote(null);
    try {
      const result = await recommendCognisphereFromGoal({ goal });
      const domains = result.recommended_domains || [];
      setRecommendedDomains(domains);
      setSelectedDomains(domains);
      if (domains.length === 0) {
        setCsphereError(
          tr(
            "没有找到匹配课程，请换一种说法试试",
            "No matching courses found. Try rephrasing your goal.",
          ),
        );
      } else {
        setCsphereNote(
          tr(
            `已匹配 ${domains.length} 门课程`,
            `Matched ${domains.length} courses`,
          ),
        );
      }
    } catch (err) {
      setCsphereError(
        err instanceof Error
          ? err.message
          : tr("推荐课程失败", "Could not find courses"),
      );
    } finally {
      setCsphereBusy(false);
    }
  }, [goalText, tr]);

  const handleGoalComposeAndSeed = useCallback(async () => {
    const goal = goalText.trim();
    if (!goal) {
      setCsphereError(
        tr("请先输入学习目标", "Enter a learning goal first"),
      );
      return;
    }
    setCsphereBusy(true);
    setCsphereError(null);
    setCsphereNote(null);
    try {
      const result = await recommendCognisphereFromGoal({
        goal,
        composeAndSeed: true,
      });
      const domains = result.recommended_domains || [];
      setRecommendedDomains(domains);
      setSelectedDomains(domains);
      const seeded = result.compose_seed;
      setCsphereNote(
        tr(
          `已根据你的目标添加 ${seeded?.seeded_count ?? result.seeded_count ?? 0} 门课程`,
          `Added ${seeded?.seeded_count ?? result.seeded_count ?? 0} courses for your goal`,
        ),
      );
      await loadList();
      const firstPath = seeded?.seeds?.find(
        (s) => "mastery_path" in s && s.mastery_path?.path_id,
      );
      if (firstPath && "mastery_path" in firstPath) {
        setSelected(firstPath.mastery_path!.path_id);
      } else if (result.continue_in_chat) {
        /* keep list refresh only */
      }
    } catch (err) {
      setCsphereError(
        err instanceof Error
          ? err.message
          : tr("生成学习路径失败", "Could not create the learning path"),
      );
    } finally {
      setCsphereBusy(false);
    }
  }, [goalText, loadList, tr]);

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

  const validPluginCount = (csphere?.plugins || []).filter(
    (plugin) => plugin.valid && plugin.kind !== "twin",
  ).length;
  // Twin packs are runtime façades, not import-and-seed course packs.
  const coursePacks = (csphere?.plugins || []).filter(
    (plugin) => plugin.kind !== "twin" && !plugin.domain.endsWith("_twin"),
  );
  const hasBundledCourses = coursePacks.some(
    (plugin) => plugin.source === "bundled_pack",
  );
  const hasExternalCourses = coursePacks.some(
    (plugin) => plugin.source !== "bundled_pack",
  );
  const twinReady = Boolean(awsTwinGate?.ok);

  return (
    <div className="flex h-full">
      <aside className="w-64 shrink-0 border-r border-[var(--border)] flex flex-col">
        <header className="px-4 py-3 border-b border-[var(--border)]">
          <div className="flex items-center gap-2 text-[var(--foreground)]">
            <GraduationCap className="w-4 h-4" />
            <h1 className="text-sm font-semibold">
              {tr("学习路径", "Learning Paths")}
            </h1>
          </div>
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">
            {tr(
              "按课程进度继续学习和复习",
              "Continue courses and review progress",
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
                "还没有课程。请从下方课程库添加一门课程开始学习。",
                "No courses yet. Add a course from the library below to start learning.",
              )}
            </p>
          ) : (
            paths.map((path) => (
              <button
                key={path.book_id}
                onClick={() => {
                  setMainPanel("map");
                  setSelected(path.book_id);
                }}
                className={`w-full text-left px-3 py-2 rounded-md transition-colors cursor-pointer ${
                  mainPanel === "map" && selected === path.book_id
                    ? "bg-[var(--primary)]/10 ring-1 ring-[var(--primary)]/30"
                    : "hover:bg-[var(--accent)]"
                }`}
              >
                <div className="truncate text-sm text-[var(--foreground)]">
                  {path.name}
                </div>
                <div className="mt-0.5 text-xs text-[var(--muted-foreground)]">
                  {isCognispherePathId(path.book_id) && (
                    <span className="mr-1 text-[var(--primary)]">
                      {tr("课程 ·", "Course ·")}
                    </span>
                  )}
                  {path.kp_count} {tr("个知识点", "objectives")} ·{" "}
                  {path.avg_mastery_pct}%
                </div>
              </button>
            ))
          )}
        </div>

        <div className="border-t border-[var(--border)] p-2 space-y-2">
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-1.5 text-xs font-medium text-[var(--foreground)]">
            <Package className="w-3.5 h-3.5" />
              {tr("课程库", "Course Library")}
            </div>
            <button
              type="button"
              disabled={csphereBusy || validPluginCount === 0}
              onClick={handleImportAvailableDomains}
              className="text-[10px] text-[var(--primary)] hover:underline disabled:opacity-50 cursor-pointer"
            >
              {tr("添加全部", "Add all")}
            </button>
          </div>
          <div className="space-y-1.5 px-0.5">
            <label className="block text-[11px] font-medium text-[var(--foreground)] leading-relaxed">
              {tr(
                "告诉 Tutor 你想学什么",
                "Tell Tutor what you want to learn",
              )}
            </label>
            <textarea
              value={goalText}
              onChange={(e) => setGoalText(e.target.value)}
              rows={2}
              disabled={csphereBusy}
              placeholder={tr(
                "例如：我是 AWS 新手，想从零开始准备初级认证…",
                "e.g. I am new to AWS and want to prepare from the beginning…",
              )}
              className="w-full resize-none rounded-md border border-[var(--border)] bg-transparent px-2 py-1.5 text-xs text-[var(--foreground)] placeholder:text-[var(--muted-foreground)]"
            />
            <div className="flex gap-1">
              <button
                type="button"
                disabled={csphereBusy || !goalText.trim()}
                onClick={handleRecommendGoal}
                className="flex-1 px-2 py-1 text-[11px] rounded-md border border-[var(--border)] hover:bg-[var(--accent)] disabled:opacity-50 cursor-pointer"
              >
                {tr("推荐课程", "Find courses")}
              </button>
              <button
                type="button"
                disabled={csphereBusy || !goalText.trim()}
                onClick={handleGoalComposeAndSeed}
                className="flex-1 px-2 py-1 text-[11px] rounded-md border border-[var(--primary)]/40 text-[var(--primary)] hover:bg-[var(--primary)]/10 disabled:opacity-50 cursor-pointer"
              >
                {tr("生成学习路径", "Create path")}
              </button>
            </div>
            {recommendedDomains.length > 0 && (
              <p className="text-[10px] text-[var(--muted-foreground)]">
                {tr("已为你匹配课程", "Matched courses")}:{" "}
                {recommendedDomains.join(", ")}
              </p>
            )}
          </div>
          {csphereError && (
            <p className="px-1 text-[10px] leading-relaxed text-red-500/90">
              {csphereError}
            </p>
          )}
          {csphereNote && (
            <p className="px-1 text-[10px] leading-relaxed text-[var(--muted-foreground)]">
              {csphereNote}
            </p>
          )}
          {csphere && !csphere.ok && validPluginCount === 0 && (
            <p className="px-1 text-[10px] leading-relaxed text-[var(--muted-foreground)]">
              {tr(
                "课程库暂时不可用，请稍后重试。",
                "The course library is not available right now. Please try again later.",
              )}
            </p>
          )}
          <div className="rounded-md border border-[var(--border)] px-2 py-2 space-y-2">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="flex items-center gap-1.5 text-xs font-medium text-[var(--foreground)]">
                  <Cpu className="w-3.5 h-3.5" />
                  {tr("AI Infra Mastery", "AI Infra Mastery")}
                </div>
                <div className="mt-0.5 text-[10px] text-[var(--muted-foreground)] leading-relaxed">
                  {tr(
                    "先进入标准学习路径，再使用孪生 Lab 收集证据。",
                    "Start with the standard learning path, then use Twin labs for evidence.",
                  )}
                </div>
              </div>
              <span className="shrink-0 text-[10px] text-green-600">
                {tr("学习优先", "Learn first")}
              </span>
            </div>
            <div className="flex gap-1">
              <button
                type="button"
                disabled={aiInfraBusy || csphereBusy}
                onClick={() => void handleContinueAiInfraMasteryPath()}
                className="flex-1 flex items-center justify-center gap-1 px-2 py-1 text-[11px] rounded-md border border-[var(--primary)]/40 text-[var(--primary)] hover:bg-[var(--primary)]/10 disabled:opacity-50 cursor-pointer"
              >
                {aiInfraBusy ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <MessageSquare className="w-3 h-3" />
                )}
                {tr("进入标准学习", "Open standard learning")}
              </button>
              <button
                type="button"
                disabled={aiInfraBusy}
                onClick={() => router.push("/space/ai-infra")}
                className="px-2 py-1 text-[11px] rounded-md border border-[var(--border)] hover:bg-[var(--accent)] disabled:opacity-50 cursor-pointer"
                title={tr("打开 AI Infra Twin Lab Console", "Open AI Infra Twin Lab Console")}
              >
                <Package className="w-3 h-3" />
              </button>
            </div>
          </div>
          <div
            className={`rounded-md border px-2 py-2 space-y-2 ${
              mainPanel === "aws-twin"
                ? "border-[var(--primary)]/50 bg-[var(--primary)]/5"
                : "border-[var(--border)]"
            }`}
          >
            <button
              type="button"
              onClick={openAwsTwinPanel}
              className="w-full flex items-start justify-between gap-2 text-left cursor-pointer"
              title={tr(
                "在右侧查看 AWS Digital Twin 练习面板",
                "Open AWS Digital Twin practice panel on the right",
              )}
            >
              <div className="min-w-0">
                <div className="text-xs font-medium text-[var(--foreground)]">
                  {tr("AWS Digital Twin Mastery", "AWS Digital Twin Mastery")}
                </div>
                <div className="mt-0.5 text-[10px] text-[var(--muted-foreground)] leading-relaxed">
                  {twinReady
                    ? tr(
                        `${twinModeLabel(awsTwinGate?.runtime_mode)} · 点击标题或「跑离线练习」在右侧查看`,
                        `${twinModeLabel(awsTwinGate?.runtime_mode)} · click title or Run to open the right panel`,
                      )
                    : tr(
                        "需服务进程设置 COGNISPHERE_LEARNING_PLUGINS_ROOT",
                        "Requires COGNISPHERE_LEARNING_PLUGINS_ROOT on the Tutor process",
                      )}
                </div>
              </div>
              <span
                className={`shrink-0 text-[10px] ${
                  twinReady ? "text-green-600" : "text-[var(--muted-foreground)]"
                }`}
              >
                {twinReady
                  ? tr("就绪", "Ready")
                  : tr("未就绪", "Not ready")}
              </span>
            </button>
            {awsTwinResult?.ok && (
              <p className="text-[10px] text-green-700/90 leading-relaxed">
                {tr(
                  `最近一次练习：${awsTwinResult.status || "complete"}`,
                  `Last practice: ${awsTwinResult.status || "complete"}`,
                )}
              </p>
            )}
            <div className="flex gap-1">
              <button
                type="button"
                disabled={awsTwinBusy || csphereBusy || !twinReady}
                onClick={() => void handleRunAwsTwinMastery()}
                className="flex-1 flex items-center justify-center gap-1 px-2 py-1 text-[11px] rounded-md border border-[var(--primary)]/40 text-[var(--primary)] hover:bg-[var(--primary)]/10 disabled:opacity-50 cursor-pointer"
              >
                {awsTwinBusy ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <Sparkles className="w-3 h-3" />
                )}
                {tr("跑离线练习", "Run offline practice")}
              </button>
              <button
                type="button"
                disabled={awsTwinBusy || csphereBusy}
                onClick={() => {
                  openAwsTwinPanel();
                  void handleAwsLearningTwinHandshake();
                }}
                className="px-2 py-1 text-[11px] rounded-md border border-[var(--border)] hover:bg-[var(--accent)] disabled:opacity-50 cursor-pointer"
                title={tr(
                  "Handshake + Learning→Twin（learn_then_practice）",
                  "Handshake + Learning→Twin (learn_then_practice)",
                )}
              >
                <Package className="w-3 h-3" />
              </button>
              <button
                type="button"
                disabled={awsTwinBusy || csphereBusy}
                onClick={() => void handleContinueAwsMasteryPath()}
                className="px-2 py-1 text-[11px] rounded-md border border-[var(--border)] hover:bg-[var(--accent)] disabled:opacity-50 cursor-pointer"
                title={tr(
                  "导入 AWS 认证课程并进入 Mastery Path 对话",
                  "Import AWS certification path and open Mastery Chat",
                )}
              >
                <MessageSquare className="w-3 h-3" />
              </button>
            </div>
          </div>
          {coursePacks.length > 0 && (
            <p className="px-1 text-[10px] leading-relaxed text-[var(--muted-foreground)]">
              {tr("课程来源", "Course source")}:{" "}
              {hasExternalCourses
                ? tr("本地知识包", "local course packs")
                : hasBundledCourses
                  ? tr("随 Tutor 安装", "included with Tutor")
                  : tr("已连接课程库", "connected course library")}
            </p>
          )}
          {coursePacks.length > 0 && (
            <div className="space-y-1.5">
              {coursePacks.map((plugin) => {
                const path = plugin.path_id
                  ? paths.find((item) => item.book_id === plugin.path_id)
                  : null;
                const label =
                  plugin.display_name || plugin.plugin_id || plugin.domain;
                const courseTitle = label
                  .replace(/\s*Domain Learning Plugin\b/i, "")
                  .replace(/\s*Learning Pack\b.*$/i, "")
                  .replace(/\s*\(thin-complete\)\s*/i, "")
                  .trim();
                const bundled = plugin.source === "bundled_pack";
                return (
                  <div
                    key={`launch-${plugin.domain}`}
                    className={`rounded-md border px-2 py-2 ${
                      selectedDomains.includes(plugin.domain)
                        ? "border-[var(--primary)]/50 bg-[var(--primary)]/5"
                        : "border-[var(--border)]"
                    }`}
                    title={plugin.description || courseTitle || plugin.domain}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <label className="min-w-0 flex items-start gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={selectedDomains.includes(plugin.domain)}
                          disabled={!plugin.valid || csphereBusy}
                          onChange={() => toggleDomain(plugin.domain)}
                          className="mt-0.5 shrink-0"
                        />
                        <div className="min-w-0">
                        <div className="truncate text-xs font-medium text-[var(--foreground)]">
                            {courseTitle || plugin.domain}
                        </div>
                        <div className="mt-0.5 text-[10px] text-[var(--muted-foreground)] truncate">
                          {path
                            ? tr(
                                `${path.kp_count} 个知识点 · ${path.avg_mastery_pct}%`,
                                `${path.kp_count} objectives · ${path.avg_mastery_pct}%`,
                              )
                            : bundled
                              ? tr("随 Tutor 安装", "Included with Tutor")
                              : tr("本地课程包", "Local course pack")}
                        </div>
                      </div>
                      </label>
                      <span
                        className={`shrink-0 text-[10px] ${
                          path
                            ? "text-[var(--primary)]"
                            : plugin.valid
                              ? "text-green-600"
                              : "text-[var(--muted-foreground)]"
                        }`}
                      >
                        {path
                          ? tr("学习中", "Active")
                          : plugin.valid
                            ? tr("可添加", "Available")
                            : tr("不可用", "Unavailable")}
                      </span>
                    </div>
                    <div className="mt-2 flex gap-1">
                      {path?.book_id ? (
                        <a
                          href={masteryChatHref(path.book_id, {
                            autoStart: "next",
                          })}
                          className="flex-1 flex items-center justify-center gap-1 px-2 py-1 text-[11px] rounded-md border border-[var(--primary)]/40 text-[var(--primary)] hover:bg-[var(--primary)]/10 cursor-pointer"
                        >
                          <GraduationCap className="w-3 h-3" />
                          {tr("继续学习", "Continue")}
                        </a>
                      ) : (
                        <button
                          type="button"
                          disabled={csphereBusy || !plugin.valid}
                          onClick={() => handleImportDomain(plugin.domain)}
                          className="flex-1 flex items-center justify-center gap-1 px-2 py-1 text-[11px] rounded-md border border-[var(--primary)]/40 text-[var(--primary)] hover:bg-[var(--primary)]/10 disabled:opacity-50 cursor-pointer"
                        >
                          {csphereBusy ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <GraduationCap className="w-3 h-3" />
                          )}
                          {tr("添加课程", "Add course")}
                        </button>
                      )}
                      {path?.book_id ? (
                        <a
                          href={masteryChatHref(path.book_id, {
                            autoStart: "next",
                          })}
                          className="px-2 py-1 text-[11px] rounded-md border border-[var(--border)] hover:bg-[var(--accent)] cursor-pointer"
                          title={tr("进入 Mastery 对话", "Open Mastery Chat")}
                        >
                          <MessageSquare className="w-3 h-3" />
                        </a>
                      ) : (
                        <button
                          type="button"
                          disabled
                          className="px-2 py-1 text-[11px] rounded-md border border-[var(--border)] disabled:opacity-50 cursor-pointer"
                          title={tr("先添加课程", "Add the course first")}
                        >
                          <MessageSquare className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          {!coursePacks.length && !csphereError && (
            <p className="px-1 text-[10px] text-[var(--muted-foreground)]">
              {tr("暂无可添加课程", "No courses available")}
            </p>
          )}
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
              `添加所选课程 (${selectedDomains.length})`,
              `Add selected courses (${selectedDomains.length})`,
            )}
          </button>
        </div>

        <footer className="p-2 border-t border-[var(--border)]">
          <a
            href={
              selected
                ? masteryChatHref(selected, { autoStart: "next" })
                : "/home?capability=mastery_path"
            }
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-sm rounded-md bg-[var(--primary)] text-[var(--primary-foreground)] hover:opacity-90 transition-opacity cursor-pointer"
          >
            <MessageSquare className="w-3.5 h-3.5" />
            {tr("继续下一步", "Continue next step")}
          </a>
        </footer>
      </aside>

      <section className="flex-1 overflow-y-auto">
        {mainPanel === "aws-twin" ? (
          <AwsTwinPracticeView
            tr={tr}
            busy={awsTwinBusy}
            ready={twinReady}
            gate={awsTwinGate}
            result={awsTwinResult}
            modeLabel={twinModeLabel(
              awsTwinResult?.runtime_mode || awsTwinGate?.runtime_mode,
            )}
            note={csphereNote}
            error={csphereError}
            onRun={() => void handleRunAwsTwinMastery()}
            onHandshake={() => void handleAwsLearningTwinHandshake()}
            onContinueChat={() => void handleContinueAwsMasteryPath()}
            onBackToMap={() => setMainPanel("map")}
          />
        ) : loadingDetail ? (
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
            radar={radar}
            zh={!!zh}
            tr={tr}
            cognisphere={selected ? isCognispherePathId(selected) : false}
            showAwsTwin={
              domainFromCognispherePathId(selected || "") === "aws_certification"
            }
            awsTwinBusy={awsTwinBusy}
            twinReady={twinReady}
            focusHint={focusHint}
            planHint={planHint}
            tutorBusy={tutorBusy}
            onContinue={() =>
              selected &&
              router.push(masteryChatHref(selected, { autoStart: "next" }))
            }
            onSocratic={handleSocraticPractice}
            onAwsTwinPractice={() => void handleRunAwsTwinMastery()}
            onAwsHandshake={() => {
              openAwsTwinPanel();
              void handleAwsLearningTwinHandshake();
            }}
            onRedo={() => selected && handleRedo(selected)}
            onRestore={() => selected && handleRestore(selected)}
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

function AbilityRadarChart({
  axes,
  label,
}: {
  axes: { label?: string; pct: number }[];
  label: string;
}) {
  const size = 200;
  const cx = size / 2;
  const cy = size / 2;
  const radius = 72;
  const n = Math.max(axes.length, 3);
  const display =
    axes.length >= 3
      ? axes
      : [
          ...axes,
          ...Array.from({ length: 3 - axes.length }, (_, i) => ({
            label: `·${i}`,
            pct: 0,
          })),
        ];
  const point = (index: number, pct: number) => {
    const angle = -Math.PI / 2 + (index / n) * Math.PI * 2;
    const r = (Math.max(0, Math.min(100, pct)) / 100) * radius;
    return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)] as const;
  };
  const grid = [0.25, 0.5, 0.75, 1].map((scale) =>
    Array.from({ length: n }, (_, i) => {
      const angle = -Math.PI / 2 + (i / n) * Math.PI * 2;
      return `${cx + radius * scale * Math.cos(angle)},${cy + radius * scale * Math.sin(angle)}`;
    }).join(" "),
  );
  const valuePts = display
    .slice(0, n)
    .map((axis, i) => point(i, axis.pct).join(","))
    .join(" ");

  return (
    <div className="flex flex-col items-center gap-2">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={label}
        className="text-[var(--foreground)]"
      >
        {grid.map((pts, i) => (
          <polygon
            key={i}
            points={pts}
            fill="none"
            stroke="currentColor"
            strokeOpacity={0.12}
            strokeWidth={1}
          />
        ))}
        {Array.from({ length: n }, (_, i) => {
          const [x, y] = point(i, 100);
          return (
            <line
              key={`spoke-${i}`}
              x1={cx}
              y1={cy}
              x2={x}
              y2={y}
              stroke="currentColor"
              strokeOpacity={0.12}
            />
          );
        })}
        <polygon
          points={valuePts}
          fill="var(--primary)"
          fillOpacity={0.22}
          stroke="var(--primary)"
          strokeWidth={1.5}
        />
        {display.slice(0, n).map((axis, i) => {
          const [x, y] = point(i, 112);
          return (
            <text
              key={`lbl-${i}`}
              x={x}
              y={y}
              textAnchor="middle"
              dominantBaseline="middle"
              className="fill-[var(--muted-foreground)]"
              fontSize={9}
            >
              {(axis.label || "").slice(0, 14)}
            </text>
          );
        })}
      </svg>
    </div>
  );
}

function MapView({
  result,
  radar,
  zh,
  tr,
  cognisphere,
  showAwsTwin,
  awsTwinBusy,
  twinReady,
  focusHint,
  planHint,
  tutorBusy,
  onContinue,
  onSocratic,
  onAwsTwinPractice,
  onAwsHandshake,
  onRedo,
  onRestore,
  onDelete,
}: {
  result: MasteryMapResult;
  radar: AbilityRadarResult | null;
  zh: boolean;
  tr: (cn: string, en: string) => string;
  cognisphere: boolean;
  showAwsTwin?: boolean;
  awsTwinBusy?: boolean;
  twinReady?: boolean;
  focusHint: string | null;
  planHint: string | null;
  tutorBusy: boolean;
  onContinue: () => void;
  onSocratic: () => void;
  onAwsTwinPractice?: () => void;
  onAwsHandshake?: () => void;
  onRedo: () => void;
  onRestore: () => void;
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
  const selectedRadar = radar?.selected;
  const radarAxes =
    selectedRadar?.axes?.filter((a) => (a.total ?? 0) > 0) ??
    map.modules.map((m) => ({
      label: m.name,
      pct: m.total ? Math.round((m.mastered / m.total) * 100) : 0,
      total: m.total,
    }));
  const weakAreas = selectedRadar?.weak_areas ?? [];

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
              <span className="text-[var(--primary)]">
                {tr("· Cognisphere", "· Cognisphere")}
              </span>
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
            onClick={onRestore}
            title={tr("恢复最近备份", "Restore latest backup")}
            className="p-1.5 rounded-md text-[var(--muted-foreground)] hover:bg-[var(--accent)] cursor-pointer"
          >
            <Undo2 className="w-4 h-4" />
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

      {(radarAxes.length > 0 || weakAreas.length > 0) && (
        <div className="mt-4 rounded-lg border border-[var(--border)] p-3">
          <div className="text-xs font-medium text-[var(--foreground)]">
            {tr("能力雷达", "Ability radar")}
            {selectedRadar?.mastered_pct != null && (
              <span className="ml-2 text-[var(--muted-foreground)] font-normal">
                {selectedRadar.mastered_pct}% {tr("域掌握", "domain mastery")}
              </span>
            )}
          </div>
          <div className="mt-2 flex flex-col sm:flex-row gap-3 items-center sm:items-start">
            {radarAxes.length > 0 && (
              <AbilityRadarChart
                axes={radarAxes}
                label={tr("模块掌握度雷达", "Module mastery radar")}
              />
            )}
            <div className="flex-1 w-full min-w-0 space-y-2">
              {(radar?.weak_domains || []).length > 1 && (
                <div>
                  <div className="text-[11px] text-[var(--muted-foreground)]">
                    {tr("薄弱域", "Weak domains")}
                  </div>
                  <ul className="mt-1 space-y-0.5">
                    {(radar?.weak_domains || []).slice(0, 4).map((d) => (
                      <li
                        key={d.path_id}
                        className="text-xs text-[var(--foreground)] truncate"
                      >
                        {d.name} · {d.mastered_pct}%
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div>
                <div className="text-[11px] text-[var(--muted-foreground)]">
                  {tr("薄弱知识点", "Weak areas")}
                </div>
                {weakAreas.length === 0 ? (
                  <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                    {tr("暂无薄弱项", "No weak areas yet")}
                  </p>
                ) : (
                  <ul className="mt-1 space-y-0.5">
                    {weakAreas.slice(0, 6).map((w) => (
                      <li
                        key={String(w.kp_id)}
                        className="text-xs text-[var(--foreground)] truncate"
                      >
                        {w.kp_name || w.kp_id}
                        <span className="text-[var(--muted-foreground)]">
                          {" "}
                          · {w.mastery_pct ?? 0}% · {w.status}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

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
          {tr("按顺序继续下一步 →", "Continue next step in order →")}
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
          {showAwsTwin && (
            <div className="flex gap-1 pt-1">
              <button
                type="button"
                onClick={onAwsTwinPractice}
                disabled={Boolean(awsTwinBusy) || !twinReady}
                className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-[11px] rounded-md border border-[var(--primary)]/40 text-[var(--primary)] hover:bg-[var(--primary)]/10 disabled:opacity-50 cursor-pointer"
              >
                {awsTwinBusy ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <Sparkles className="w-3 h-3" />
                )}
                {tr("AWS Twin 离线练习", "AWS Twin offline practice")}
              </button>
              <button
                type="button"
                onClick={onAwsHandshake}
                disabled={Boolean(awsTwinBusy)}
                className="px-2 py-1.5 text-[11px] rounded-md border border-[var(--border)] hover:bg-[var(--accent)] disabled:opacity-50 cursor-pointer"
                title={tr(
                  "Handshake + Learning→Twin",
                  "Handshake + Learning→Twin",
                )}
              >
                <Package className="w-3 h-3" />
              </button>
            </div>
          )}
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

function AwsTwinPracticeView({
  tr,
  busy,
  ready,
  gate,
  result,
  modeLabel,
  note,
  error,
  onRun,
  onHandshake,
  onContinueChat,
  onBackToMap,
}: {
  tr: (cn: string, en: string) => string;
  busy: boolean;
  ready: boolean;
  gate?: AwsTwinMasteryGate;
  result: AwsTwinMasteryResult | null;
  modeLabel: string;
  note: string | null;
  error: string | null;
  onRun: () => void;
  onHandshake: () => void;
  onContinueChat: () => void;
  onBackToMap: () => void;
}) {
  const steps = result?.steps;
  const stepEntries: { id: string; row: Record<string, unknown> }[] = [];
  if (steps && typeof steps === "object" && !Array.isArray(steps)) {
    for (const [id, row] of Object.entries(steps as Record<string, unknown>)) {
      if (row && typeof row === "object") {
        stepEntries.push({ id, row: row as Record<string, unknown> });
      }
    }
  } else if (Array.isArray(steps)) {
    for (const row of steps) {
      if (row && typeof row === "object") {
        const obj = row as Record<string, unknown>;
        stepEntries.push({
          id: String(obj.step_id || obj.capability || stepEntries.length),
          row: obj,
        });
      }
    }
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs text-[var(--muted-foreground)]">
            Cognisphere · AWS Digital Twin
          </div>
          <h2 className="mt-1 text-lg font-semibold text-[var(--foreground)]">
            {tr("AWS Digital Twin Mastery", "AWS Digital Twin Mastery")}
          </h2>
          <p className="mt-1 text-xs text-[var(--muted-foreground)] leading-relaxed">
            {tr(
              "本地模拟练习（CP-04 → CP-06 → CP-12），不连接真实 AWS / LLM。结果在此面板展示。",
              "Local simulation practice (CP-04 → CP-06 → CP-12); no live AWS / LLM. Results appear in this panel.",
            )}
          </p>
        </div>
        <button
          type="button"
          onClick={onBackToMap}
          className="shrink-0 text-[11px] px-2 py-1 rounded-md border border-[var(--border)] hover:bg-[var(--accent)] cursor-pointer"
        >
          {tr("返回地图", "Back to map")}
        </button>
      </div>

      <div className="rounded-lg border border-[var(--border)] p-3 space-y-2 text-xs">
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[var(--muted-foreground)]">
          <span>
            {tr("状态", "Status")}:{" "}
            <span className="text-[var(--foreground)]">
              {result?.status || gate?.status || (ready ? "ready" : "blocked")}
            </span>
          </span>
          <span>
            {tr("模式", "Mode")}:{" "}
            <span className="text-[var(--foreground)]">{modeLabel}</span>
          </span>
          <span>
            package:{" "}
            <span className="text-[var(--foreground)]">
              {result?.package_id || gate?.package_id || "—"}
            </span>
          </span>
          <span>
            choice:{" "}
            <span className="text-[var(--foreground)]">
              {result?.choice_id || gate?.choice_id || "—"}
            </span>
          </span>
        </div>
        {error && (
          <p className="text-red-500/90 leading-relaxed">{error}</p>
        )}
        {note && !error && (
          <p className="text-[var(--muted-foreground)] leading-relaxed">{note}</p>
        )}
        <div className="flex flex-wrap gap-2 pt-1">
          <button
            type="button"
            disabled={busy || !ready}
            onClick={onRun}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-[var(--primary)]/40 text-[var(--primary)] hover:bg-[var(--primary)]/10 disabled:opacity-50 cursor-pointer"
          >
            {busy ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Sparkles className="w-3.5 h-3.5" />
            )}
            {tr("跑离线练习", "Run offline practice")}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onHandshake}
            className="px-3 py-1.5 text-sm rounded-md border border-[var(--border)] hover:bg-[var(--accent)] disabled:opacity-50 cursor-pointer"
          >
            {tr("Handshake", "Handshake")}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onContinueChat}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md bg-[var(--primary)] text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50 cursor-pointer"
          >
            <MessageSquare className="w-3.5 h-3.5" />
            {tr("进入 Mastery 对话", "Open Mastery chat")}
          </button>
        </div>
      </div>

      {busy && !result && (
        <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)] py-8 justify-center">
          <Loader2 className="w-4 h-4 animate-spin" />
          {tr("正在运行离线练习…", "Running offline practice…")}
        </div>
      )}

      {!busy && !result && (
        <div className="rounded-lg border border-dashed border-[var(--border)] p-6 text-center text-sm text-[var(--muted-foreground)]">
          {tr(
            "点击「跑离线练习」后，这里会显示场景、服务对比、反馈与辅导回合等学习内容。",
            "Click “Run offline practice” to show the scenario, service comparison, feedback, and tutor turns.",
          )}
        </div>
      )}

      {stepEntries.length > 0 && (
        <div className="space-y-3">
          <div className="text-xs font-medium text-[var(--foreground)]">
            {tr("学习内容", "Learning content")}
          </div>
          {stepEntries.map(({ id, row }) => {
            const ok = row.ok !== false;
            const capability = String(row.capability || "");
            const learner =
              row.learner && typeof row.learner === "object"
                ? (row.learner as Record<string, unknown>)
                : null;
            const services = Array.isArray(learner?.services)
              ? (learner!.services as Record<string, unknown>[])
              : [];
            const turns = Array.isArray(learner?.turns)
              ? (learner!.turns as Record<string, unknown>[])
              : [];
            const choice =
              learner?.choice && typeof learner.choice === "object"
                ? (learner.choice as Record<string, unknown>)
                : null;
            const hasChoiceRationale = Boolean(
              choice && (choice.label || choice.choice_why),
            );
            const mistakes = Array.isArray(learner?.common_mistakes)
              ? (learner!.common_mistakes as unknown[]).map(String)
              : [];
            const title = String(
              learner?.title || learner?.package_title || id,
            );
            const problem = String(learner?.user_problem || "");
            const objective = String(learner?.learning_objective || "");
            const feedback = String(
              learner?.feedback_message || row.feedback_message || "",
            );
            const summary = String(learner?.summary || "");
            return (
              <div
                key={id}
                className="rounded-md border border-[var(--border)] px-3 py-3 space-y-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-medium text-[var(--foreground)]">
                    {title}
                    {capability ? (
                      <span className="ml-2 text-[10px] text-[var(--muted-foreground)]">
                        {capability}
                      </span>
                    ) : null}
                  </div>
                  <span
                    className={`text-[11px] ${
                      ok ? "text-green-600" : "text-red-500"
                    }`}
                  >
                    {ok ? tr("通过", "ok") : tr("失败", "failed")}
                  </span>
                </div>

                {problem && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wide text-[var(--muted-foreground)]">
                      {tr("场景", "Scenario")}
                    </div>
                    <p className="mt-0.5 text-sm text-[var(--foreground)] leading-relaxed">
                      {problem}
                    </p>
                  </div>
                )}

                {objective && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wide text-[var(--muted-foreground)]">
                      {tr("学习目标", "Objective")}
                    </div>
                    <p className="mt-0.5 text-xs text-[var(--muted-foreground)] leading-relaxed">
                      {objective}
                    </p>
                  </div>
                )}

                {services.length > 0 && (
                  <div className="space-y-2">
                    <div className="text-[10px] uppercase tracking-wide text-[var(--muted-foreground)]">
                      {tr("服务对比", "Services")}
                    </div>
                    {services.map((svc, idx) => (
                      <div
                        key={String(svc.service_id || svc.service_code || idx)}
                        className="rounded border border-[var(--border)]/70 px-2.5 py-2"
                      >
                        <div className="text-xs font-medium text-[var(--foreground)]">
                          {String(
                            svc.display_name ||
                              svc.service_code ||
                              svc.service_id ||
                              "Service",
                          )}
                        </div>
                        {svc.what ? (
                          <p className="mt-1 text-[11px] text-[var(--muted-foreground)] leading-relaxed">
                            <span className="text-[var(--foreground)]">What: </span>
                            {String(svc.what)}
                          </p>
                        ) : null}
                        {svc.why ? (
                          <p className="mt-0.5 text-[11px] text-[var(--muted-foreground)] leading-relaxed">
                            <span className="text-[var(--foreground)]">Why: </span>
                            {String(svc.why)}
                          </p>
                        ) : null}
                        {svc.when ? (
                          <p className="mt-0.5 text-[11px] text-[var(--muted-foreground)] leading-relaxed">
                            <span className="text-[var(--foreground)]">When: </span>
                            {String(svc.when)}
                          </p>
                        ) : null}
                      </div>
                    ))}
                  </div>
                )}

                {choice && hasChoiceRationale && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wide text-[var(--muted-foreground)]">
                      {tr("选择与理由", "Choice & rationale")}
                    </div>
                    <p className="mt-0.5 text-xs text-[var(--foreground)] leading-relaxed">
                      {String(choice.label || choice.choice_id || "")}
                      {choice.correct != null
                        ? ` · ${choice.correct ? tr("正确", "correct") : tr("不正确", "incorrect")}`
                        : ""}
                    </p>
                    {choice.choice_why ? (
                      <p className="mt-0.5 text-[11px] text-[var(--muted-foreground)] leading-relaxed">
                        {String(choice.choice_why)}
                      </p>
                    ) : null}
                  </div>
                )}

                {feedback && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wide text-[var(--muted-foreground)]">
                      {tr("反馈", "Feedback")}
                    </div>
                    <p className="mt-0.5 text-xs text-[var(--foreground)] leading-relaxed">
                      {feedback}
                    </p>
                  </div>
                )}

                {mistakes.length > 0 && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wide text-[var(--muted-foreground)]">
                      {tr("常见误区", "Common mistakes")}
                    </div>
                    <ul className="mt-0.5 list-disc pl-4 text-[11px] text-[var(--muted-foreground)] space-y-0.5">
                      {mistakes.map((m) => (
                        <li key={m}>{m}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {turns.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="text-[10px] uppercase tracking-wide text-[var(--muted-foreground)]">
                      {tr("苏格拉底辅导回合", "Socratic tutor turns")}
                    </div>
                    {turns.map((turn, idx) => (
                      <div
                        key={`${String(turn.phase_id || "phase")}-${idx}`}
                        className="rounded border border-[var(--border)]/70 px-2.5 py-2"
                      >
                        <div className="text-[11px] font-medium text-[var(--foreground)]">
                          {String(turn.phase_id || `turn ${idx + 1}`)}
                        </div>
                        {turn.offline_utterance ? (
                          <p className="mt-0.5 text-xs text-[var(--foreground)] leading-relaxed">
                            {String(turn.offline_utterance)}
                          </p>
                        ) : null}
                        {turn.tutor_prompt ? (
                          <p className="mt-0.5 text-[11px] text-[var(--muted-foreground)] leading-relaxed">
                            {String(turn.tutor_prompt)}
                          </p>
                        ) : null}
                      </div>
                    ))}
                  </div>
                )}

                {summary && (
                  <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
                    {summary}
                  </p>
                )}

                {!learner && (
                  <p className="text-[11px] text-[var(--muted-foreground)]">
                    {tr(
                      "此步骤暂无学习者正文（仅状态元数据）。请确认 API 已加载最新 LearningPlugins。",
                      "No learner body for this step (status metadata only). Ensure the API loads the latest LearningPlugins.",
                    )}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {result && stepEntries.length === 0 && (
        <div className="rounded-lg border border-dashed border-[var(--border)] p-4 text-sm text-[var(--muted-foreground)]">
          {tr(
            "练习已返回，但没有可展示的步骤内容。请检查 API 是否挂载 COGNISPHERE_LEARNING_PLUGINS_ROOT。",
            "Practice returned without step content. Check that the API has COGNISPHERE_LEARNING_PLUGINS_ROOT mounted.",
          )}
        </div>
      )}
    </div>
  );
}
