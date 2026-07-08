// Analytos Brain policy sketch for Omnigraph server deployments.
// Validate and adapt entity/action names against the active Omnigraph policy schema.

permit(
  principal == Actor::"ingest-agent",
  action in [Action::"branch_create", Action::"load"],
  resource == Graph::"analytos-brain"
) when { context.branch like "ingest/*" };

forbid(
  principal == Actor::"ingest-agent",
  action == Action::"branch_merge",
  resource == Graph::"analytos-brain"
);

permit(
  principal == Actor::"human-reviewer",
  action in [Action::"read", Action::"invoke_query", Action::"branch_merge", Action::"branch_delete"],
  resource == Graph::"analytos-brain"
) when { context.branch == "main" || context.branch like "ingest/*" };

permit(
  principal == Actor::"content-agent",
  action in [Action::"read", Action::"invoke_query"],
  resource == Graph::"analytos-brain"
) when { context.branch == "main" };

forbid(
  principal == Actor::"content-agent",
  action in [Action::"read", Action::"invoke_query"],
  resource == Graph::"analytos-brain"
) when { context.entity_type == "EmailThread" || context.visibility == "internal_only" };

permit(
  principal == Actor::"gtm-agent",
  action in [Action::"read", Action::"invoke_query"],
  resource == Graph::"analytos-brain"
) when { context.branch == "main" };

forbid(
  principal in [Actor::"gtm-agent", Actor::"content-agent"],
  action in [Action::"branch_create", Action::"load", Action::"branch_merge", Action::"branch_delete"],
  resource == Graph::"analytos-brain"
);
