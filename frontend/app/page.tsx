"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type SearchResult = {
  id: string;
  source: string;
  title: string;
  description: string;
  publisher: string;
  updated_at: string | null;
  formats: string[];
  license: string | null;
  url: string | null;
  can_explore: boolean;
  can_check?: boolean;
};

type SearchResponse = {
  query: string;
  total: number;
  sources: { name: string; status: "ok" | "unavailable"; count: number }[];
  results: SearchResult[];
};

type Column = {
  name: string;
  type: string;
  non_null_count?: number;
  distinct_count?: number;
  samples?: unknown[];
  suggested_roles?: string[];
};
type Dataset = {
  id: string;
  original_name: string;
  sha256: string;
  size_bytes: number;
  row_count: number;
  columns: Column[];
  preview: Record<string, unknown>[];
  catalog_source: string;
};

type ProjectSource = Omit<Dataset, "preview" | "catalog_source"> & {
  position: number;
  catalog_source?: string;
  title: string;
  publisher?: string | null;
  source_url?: string | null;
  catalog_dataset_id?: string | null;
  catalog_resource_id?: string | null;
  dimensions?: { commune: string | null; année: string | null };
};

type JoinAnalysis = {
  dimensions: string[];
  left_distinct_keys: number;
  right_distinct_keys: number;
  matched_keys: number;
  left_match_rate: number;
  right_match_rate: number;
  left_duplicate_keys: number;
  right_duplicate_keys: number;
  left_unmatched_samples: { commune: string; année: string | null }[];
  right_unmatched_samples: { commune: string; année: string | null }[];
  geography?: {
    left_communes: number;
    right_communes: number;
    matched_communes: number;
    left_match_rate: number;
    right_match_rate: number;
  };
  periods?: {
    left: { first: string; last: string; distinct_years: number };
    right: { first: string; last: string; distinct_years: number };
    matched_years: number;
  } | null;
  warnings: string[];
};

type IndicatorRow = {
  commune: string;
  année: string | null;
  source_1_value: number;
  source_2_value: number;
  value: number;
};

type IndicatorResult = {
  title: string;
  created_at: string;
  operation: "ratio_percent" | "difference";
  operation_label: string;
  unit: string;
  formula: string;
  dimensions: string[];
  dimension_matches: number;
  result_count: number;
  displayed_count: number;
  excluded_missing_values: number;
  excluded_zero_denominator: number;
  warnings: string[];
  rows: IndicatorRow[];
  sources: {
    dataset_id: string;
    title: string;
    sha256: string;
    value_column: string;
    aggregation: string;
  }[];
};

type Project = {
  id: string;
  title: string;
  created_at: string;
  sources: ProjectSource[];
  join_analysis?: JoinAnalysis | null;
  indicator?: IndicatorResult | null;
  version_count?: number;
};

type VersionSummary = {
  id: string;
  version_number: number;
  title: string;
  author_name: string;
  snapshot_sha256: string;
  created_at: string;
};

type PublicationComment = {
  id: string;
  author_name: string;
  content: string;
  created_at: string;
};

type PublishedSource = {
  position: number;
  dataset_id: string;
  title: string;
  publisher?: string | null;
  catalog_source?: string | null;
  catalog_dataset_id?: string | null;
  catalog_resource_id?: string | null;
  source_url?: string | null;
  sha256: string;
  size_bytes: number;
  row_count: number;
  columns: Column[];
  dimensions: { commune: string | null; année: string | null };
};

type PublishedVersion = {
  id: string;
  project_id: string;
  project_title: string;
  version_number: number;
  title: string;
  author_name: string;
  summary: string;
  interpretation: string;
  limitations: string;
  published_at: string;
  created_at: string;
  snapshot_sha256: string;
  integrity_verified: boolean;
  sources: PublishedSource[];
  join_analysis: JoinAnalysis;
  indicator: IndicatorResult;
  reproducibility: {
    engine: string;
    key_normalization: string;
    missing_data_policy: string;
    source_hashes: string[];
  };
  comments: PublicationComment[];
  versions: VersionSummary[];
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const examples = ["population par commune", "parc automobile", "consommation électrique"];

export default function Home() {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState<SearchResponse | null>(null);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [publication, setPublication] = useState<PublishedVersion | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [exploring, setExploring] = useState("");

  useEffect(() => {
    const parameters = new URLSearchParams(window.location.search);
    const publicationId = parameters.get("publication");
    const projectId = parameters.get("project");
    if (!publicationId && !projectId) return;
    let active = true;
    const endpoint = publicationId
      ? `${apiUrl}/api/publications/${encodeURIComponent(publicationId)}`
      : `${apiUrl}/api/projects/${encodeURIComponent(projectId!)}`;
    fetch(endpoint)
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail ?? "La fiche n’a pas pu être retrouvée.");
        if (active) {
          if (publicationId) setPublication(body);
          else setProject(body);
        }
      })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : "La fiche n’a pas pu être retrouvée.");
      });
    return () => { active = false; };
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    await runSearch(query);
  }

  async function runSearch(value: string) {
    const normalized = value.trim();
    if (normalized.length < 2) return;
    setQuery(normalized);
    setLoading(true);
    setError("");
    setDataset(null);
    try {
      const response = await fetch(`${apiUrl}/api/search?q=${encodeURIComponent(normalized)}`);
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "La recherche a échoué.");
      setSearch(body);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "La recherche a échoué.");
    } finally {
      setLoading(false);
    }
  }

  async function explore(result: SearchResult) {
    if (project && project.sources.length >= 2) return;
    const key = `${result.source}:${result.id}`;
    let endpoint: string;
    if (result.source === "data.gouv.fr") {
      endpoint = `${apiUrl}/api/catalogs/data-gouv/${encodeURIComponent(result.id)}/explore`;
    } else if (result.source === "data.europa.eu") {
      endpoint = `${apiUrl}/api/catalogs/data-europa/explore?dataset_id=${encodeURIComponent(result.id)}`;
    } else if (result.source === "Recherche Data Gouv") {
      endpoint = `${apiUrl}/api/catalogs/recherche-data-gouv/explore?persistent_id=${encodeURIComponent(result.id)}`;
    } else {
      return;
    }
    setExploring(key);
    setError("");
    try {
      const response = await fetch(endpoint, { method: "POST" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Cette ressource ne peut pas être explorée.");
      const projectResponse = await fetch(
        project ? `${apiUrl}/api/projects/${encodeURIComponent(project.id)}/sources` : `${apiUrl}/api/projects`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(
            project
              ? {
                  dataset_id: body.id,
                  source_title: result.title,
                  source_publisher: result.publisher,
                }
              : {
                  dataset_id: body.id,
                  title: `Projet : ${query || result.title}`.slice(0, 160),
                  source_title: result.title,
                  source_publisher: result.publisher,
                },
          ),
        },
      );
      const projectBody = await projectResponse.json();
      if (!projectResponse.ok) throw new Error(projectBody.detail ?? "La source n’a pas pu être ajoutée au projet.");
      setProject(projectBody);
      window.history.replaceState({}, "", `${window.location.pathname}?project=${encodeURIComponent(projectBody.id)}`);
      setDataset(body);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Cette ressource ne peut pas être explorée.");
    } finally {
      setExploring("");
    }
  }

  if (publication) return <PublishedSheet publication={publication} />;

  if (dataset) {
    return (
      <main>
        {(!project || project.sources.length < 2) && (
          <button className="back" onClick={() => setDataset(null)}>← Revenir aux résultats</button>
        )}
        <DatasetResult
          dataset={dataset}
          project={project}
          onProjectChange={setProject}
          onAddSecond={() => {
            setDataset(null);
            setSearch(null);
            setQuery("");
            window.scrollTo({ top: 0, behavior: "smooth" });
          }}
        />
      </main>
    );
  }

  if (project?.sources.length === 2) {
    return (
      <main>
        <header>
          <p className="eyebrow">Explorateur de données publiques</p>
          <h1>Vérifier que les sources parlent des mêmes lieux.</h1>
          <p className="intro">Choisissez les colonnes comparables. Le site mesure ensuite les correspondances et signale ce qui demande votre attention.</p>
        </header>
        <Journey project={project} />
        <ProjectSources project={project} />
        <section className="dataset-view workspace-view">
          <ColumnQualification project={project} onProjectChange={setProject} />
        </section>
      </main>
    );
  }

  return (
    <main>
      <header>
        <p className="eyebrow">Explorateur de données publiques</p>
        <h1>{project ? "Trouver une deuxième source." : "Trouver les faits derrière une question."}</h1>
        <p className="intro">{project
          ? "Votre première source est conservée. Cherchez maintenant les données à mettre en regard."
          : "Écrivez simplement ce que vous cherchez. Le site s’occupe de trouver et d’ouvrir les fichiers techniques."}</p>
      </header>

      <Journey project={project} />

      {project && <ProjectSources project={project} compact />}

      <section className="search-card" aria-label="Recherche de données publiques">
        <form className="search-form" onSubmit={submit}>
          <label htmlFor="search">Quelles données recherchez-vous ?</label>
          <div className="search-row">
            <input
              id="search"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Ex. nombre de voitures par commune"
              autoComplete="off"
            />
            <button disabled={query.trim().length < 2 || loading}>{loading ? "Recherche…" : "Rechercher"}</button>
          </div>
        </form>
        <div className="examples">
          <span>Exemples</span>
          {examples.map((example) => <button key={example} onClick={() => runSearch(example)}>{example}</button>)}
        </div>
      </section>

      {error && <p className="error" role="alert">{error}</p>}
      {search && (
        <SearchResults
          search={search}
          exploring={exploring}
          onExplore={explore}
          addingSecond={Boolean(project)}
        />
      )}
    </main>
  );
}

function SearchResults({
  search,
  exploring,
  onExplore,
  addingSecond,
}: {
  search: SearchResponse;
  exploring: string;
  onExplore: (result: SearchResult) => void;
  addingSecond: boolean;
}) {
  return (
    <section className="search-results">
      <div className="results-heading">
        <div>
          <p className="eyebrow">Résultats</p>
          <h2>{search.total} jeux de données utilisables pour « {search.query} »</h2>
        </div>
        <div className="source-status">
          {search.sources.map((source) => (
            <span className={source.status} key={source.name}>
              <i />{source.name} · {source.status === "ok" ? source.count : "indisponible"}
            </span>
          ))}
        </div>
      </div>
      <div className="results-grid">
        {search.results.map((result) => (
          <ResultCard
            key={`${result.source}:${result.id}`}
            result={result}
            exploring={exploring}
            onExplore={onExplore}
            addingSecond={addingSecond}
          />
        ))}
      </div>
    </section>
  );
}

function Journey({ project }: { project: Project | null }) {
  return (
    <div className="journey" aria-label="Parcours de création">
      <span className="active"><b>1</b>Trouver des données</span>
      <span className={project ? "active" : ""}><b>2</b>Ajouter une deuxième source</span>
      <span className={project?.sources.length === 2 ? "active" : ""}><b>3</b>Vérifier le croisement</span>
      <span className={project?.indicator ? "active" : ""}><b>4</b>Créer un indicateur</span>
      <span className={(project?.version_count ?? 0) > 0 ? "active" : ""}><b>5</b>Publier une fiche</span>
    </div>
  );
}

function ResultCard({
  result,
  exploring,
  onExplore,
  addingSecond,
}: {
  result: SearchResult;
  exploring: string;
  onExplore: (result: SearchResult) => void;
  addingSecond: boolean;
}) {
  if (!result.can_explore && !result.can_check) return null;
  const key = `${result.source}:${result.id}`;
  return (
    <article className="result-card">
      <div className="card-topline">
        <span className="source-badge">{result.source}</span>
        {result.updated_at && <time>Mise à jour {formatDate(result.updated_at)}</time>}
      </div>
      <h3>{result.title}</h3>
      <p className="publisher">{result.publisher}</p>
      <p className="description">{result.description}</p>
      <div className="formats">
        {result.formats.length ? result.formats.map((format) => <span key={format}>{format}</span>) : <span>Format non précisé</span>}
        {result.license && <span>Licence {result.license}</span>}
      </div>

      <div className="card-actions">
        <button onClick={() => onExplore(result)} disabled={exploring === key}>
          {exploring === key
            ? "Préparation des données…"
              : result.can_check
                ? "Vérifier et utiliser"
                : addingSecond
                  ? "Ajouter comme 2e source"
                  : "Utiliser ces données"}
        </button>
        {result.url && <a href={result.url} target="_blank" rel="noreferrer">Voir la fiche source ↗</a>}
      </div>
    </article>
  );
}

function DatasetResult({
  dataset,
  project,
  onAddSecond,
  onProjectChange,
}: {
  dataset: Dataset;
  project: Project | null;
  onAddSecond: () => void;
  onProjectChange: (project: Project) => void;
}) {
  return (
    <section className="dataset-view">
      <p className="eyebrow">Ressource publique explorée</p>
      <h1>{dataset.original_name}</h1>
      <p className="intro">Le site a choisi la ressource tabulaire, l’a récupérée et l’a ouverte automatiquement. Vous n’avez aucun fichier à manipuler.</p>
      <div className="summary">
        <div><span>Lignes</span><strong>{dataset.row_count.toLocaleString("fr-FR")}</strong></div>
        <div><span>Colonnes</span><strong>{dataset.columns.length}</strong></div>
        <div><span>Taille</span><strong>{formatSize(dataset.size_bytes)}</strong></div>
        <div><span>Origine</span><strong>{dataset.catalog_source}</strong></div>
      </div>
      <div className="hash"><span>Empreinte SHA-256</span><code>{dataset.sha256}</code></div>

      {project && (
        <>
          <ProjectSources project={project} />
          {project.sources.length < 2 ? (
            <button className="add-source" onClick={onAddSecond}>Ajouter une deuxième source</button>
          ) : (
            <ColumnQualification project={project} onProjectChange={onProjectChange} />
          )}
        </>
      )}

      <h2>Structure détectée</h2>
      <div className="columns">
        {dataset.columns.map((column) => <div key={column.name}><strong>{column.name}</strong><span>{column.type}</span></div>)}
      </div>

      <h2>Aperçu des 20 premières lignes</h2>
      <div className="table-wrap">
        <table>
          <thead><tr>{dataset.columns.map((column) => <th key={column.name}>{column.name}</th>)}</tr></thead>
          <tbody>{dataset.preview.map((row, index) => <tr key={index}>{dataset.columns.map((column) => <td key={column.name}>{String(row[column.name] ?? "")}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </section>
  );
}

function ProjectSources({ project, compact = false }: { project: Project; compact?: boolean }) {
  return (
    <section className={`project-sources${compact ? " compact" : ""}`} aria-label="Sources du projet">
      <div className="project-title">
        <p className="eyebrow">Projet en cours</p>
        <h2>{project.title}</h2>
      </div>
      <div className="source-slots">
        {[0, 1].map((index) => {
          const source = project.sources[index];
          return source ? (
            <div className="source-slot filled" key={source.id}>
              <span>Source {index + 1}</span>
              <strong>{source.title}</strong>
              <small>{source.publisher ? `${source.publisher} · ` : ""}{source.catalog_source ?? "Source publique"} · {source.row_count.toLocaleString("fr-FR")} lignes</small>
            </div>
          ) : (
            <div className="source-slot" key={`empty-${index}`}>
              <span>Source {index + 1}</span>
              <strong>À rechercher</strong>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ColumnQualification({
  project,
  onProjectChange,
}: {
  project: Project;
  onProjectChange: (project: Project) => void;
}) {
  const [qualified, setQualified] = useState<Project | null>(null);
  const [choices, setChoices] = useState<Record<string, { commune: string; year: string }>>({});
  const [join, setJoin] = useState<JoinAnalysis | null>(project.join_analysis ?? null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function loadQualification() {
      try {
        const response = await fetch(`${apiUrl}/api/projects/${encodeURIComponent(project.id)}/qualification`);
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail ?? "Les colonnes n’ont pas pu être analysées.");
        if (!active) return;
        const analyzed = body as Project;
        const initial = Object.fromEntries(analyzed.sources.map((source) => [
          source.id,
          {
            commune: source.dimensions?.commune ?? bestSuggestedColumn(source.columns, "commune"),
            year: source.dimensions?.année ?? bestSuggestedColumn(source.columns, "année"),
          },
        ]));
        setQualified(analyzed);
        setChoices(initial);
        setJoin(analyzed.join_analysis ?? null);
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : "Les colonnes n’ont pas pu être analysées.");
      } finally {
        if (active) setLoading(false);
      }
    }
    loadQualification();
    return () => { active = false; };
  }, [project.id]);

  async function verifyJoin() {
    if (!qualified || qualified.sources.some((source) => !choices[source.id]?.commune)) {
      setError("Choisissez une colonne commune dans chaque source.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const dimensionsResponse = await fetch(
        `${apiUrl}/api/projects/${encodeURIComponent(project.id)}/dimensions`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sources: qualified.sources.map((source) => ({
              dataset_id: source.id,
              commune_column: choices[source.id].commune,
              year_column: choices[source.id].year || null,
            })),
          }),
        },
      );
      const savedProject = await dimensionsResponse.json();
      if (!dimensionsResponse.ok) throw new Error(savedProject.detail ?? "Les choix n’ont pas pu être enregistrés.");

      const analysisResponse = await fetch(
        `${apiUrl}/api/projects/${encodeURIComponent(project.id)}/join-analysis`,
        { method: "POST" },
      );
      const analysis = await analysisResponse.json();
      if (!analysisResponse.ok) throw new Error(analysis.detail ?? "Le croisement n’a pas pu être vérifié.");
      setJoin(analysis);
      onProjectChange({ ...savedProject, join_analysis: analysis });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Le croisement n’a pas pu être vérifié.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="qualification-loading" role="status">Analyse des colonnes…</p>;
  if (!qualified) return <p className="error" role="alert">{error}</p>;
  const missingYear = qualified.sources.some((source) => !choices[source.id]?.year);

  return (
    <section className="qualification" aria-labelledby="qualification-title">
      <div className="qualification-heading">
        <div>
          <p className="eyebrow">Étape 3</p>
          <h2 id="qualification-title">Quelles colonnes désignent le même lieu ?</h2>
        </div>
        <p>Les suggestions sont automatiques. Vérifiez-les à partir des exemples avant de continuer.</p>
      </div>

      <div className="qualification-grid">
        {qualified.sources.map((source, index) => {
          const selection = choices[source.id] ?? { commune: "", year: "" };
          return (
            <fieldset className="qualification-source" key={source.id}>
              <legend>Source {index + 1} · {source.title}</legend>
              <label>
                Colonne de la commune
                <select
                  value={selection.commune}
                  onChange={(event) => setChoices((current) => ({
                    ...current,
                    [source.id]: { ...selection, commune: event.target.value },
                  }))}
                >
                  <option value="">Choisir une colonne</option>
                  {source.columns.map((column) => (
                    <option value={column.name} key={column.name}>
                      {column.name}{column.suggested_roles?.includes("commune") ? " · suggérée" : ""}
                    </option>
                  ))}
                </select>
              </label>
              <ColumnDetails column={source.columns.find((column) => column.name === selection.commune)} />

              <label>
                Colonne de l’année
                <select
                  value={selection.year}
                  onChange={(event) => setChoices((current) => ({
                    ...current,
                    [source.id]: { ...selection, year: event.target.value },
                  }))}
                >
                  <option value="">Aucune année dans cette source</option>
                  {source.columns.map((column) => (
                    <option value={column.name} key={column.name}>
                      {column.name}{column.suggested_roles?.includes("année") ? " · suggérée" : ""}
                    </option>
                  ))}
                </select>
              </label>
              <ColumnDetails column={source.columns.find((column) => column.name === selection.year)} />
            </fieldset>
          );
        })}
      </div>

      {missingYear && (
        <p className="quality-note">
          Une année manque dans au moins une source. Elle ne sera pas inventée : le premier contrôle portera seulement sur la commune.
        </p>
      )}
      {error && <p className="error" role="alert">{error}</p>}
      <button onClick={verifyJoin} disabled={saving}>
        {saving ? "Vérification du croisement…" : "Vérifier le croisement"}
      </button>
      {join && (
        <>
          <JoinQuality analysis={join} sources={qualified.sources} />
          {join.matched_keys > 0 ? (
            <IndicatorBuilder
              project={qualified}
              existing={qualified.indicator ?? project.indicator ?? null}
              onIndicatorChange={(indicator) => {
                setQualified((current) => current ? { ...current, indicator } : current);
                onProjectChange({ ...project, join_analysis: join, indicator });
              }}
            />
          ) : (
            <p className="indicator-blocked">
              Aucun indicateur ne sera calculé avec ces choix, car aucune commune ne correspond. Changez les colonnes ou remplacez une source.
            </p>
          )}
        </>
      )}
    </section>
  );
}

function ColumnDetails({ column }: { column?: Column }) {
  if (!column) return <p className="column-help">Choisissez une colonne pour voir des exemples.</p>;
  const samples = column.samples?.map((sample) => String(sample)).join(" · ") || "aucune valeur";
  return (
    <p className="column-help">
      <span>{translateType(column.type)}</span>
      <span>{column.distinct_count?.toLocaleString("fr-FR")} valeurs différentes</span>
      <strong>Exemples : {samples}</strong>
    </p>
  );
}

function JoinQuality({ analysis, sources }: { analysis: JoinAnalysis; sources: ProjectSource[] }) {
  return (
    <section className="join-quality" aria-labelledby="join-title">
      <div className="join-heading">
        <div>
          <p className="eyebrow">Contrôle du croisement</p>
          <h3 id="join-title">{analysis.matched_keys.toLocaleString("fr-FR")} clés correspondent</h3>
        </div>
        <span>Sur {analysis.dimensions.join(" + ")}</span>
      </div>
      <div className="match-metrics">
        <div><span>Source 1 retrouvée</span><strong>{analysis.left_match_rate.toLocaleString("fr-FR")} %</strong></div>
        <div><span>Source 2 retrouvée</span><strong>{analysis.right_match_rate.toLocaleString("fr-FR")} %</strong></div>
        <div><span>Clés répétées</span><strong>{analysis.left_duplicate_keys + analysis.right_duplicate_keys}</strong></div>
      </div>
      {(analysis.geography || analysis.periods) && (
        <div className="scope-diagnostics">
          {analysis.geography && (
            <p><strong>Communes :</strong> {analysis.geography.matched_communes.toLocaleString("fr-FR")} communes communes aux deux sources, sur {analysis.geography.left_communes.toLocaleString("fr-FR")} et {analysis.geography.right_communes.toLocaleString("fr-FR")}.</p>
          )}
          {analysis.periods && (
            <p><strong>Années :</strong> source 1 de {analysis.periods.left.first} à {analysis.periods.left.last} ; source 2 de {analysis.periods.right.first} à {analysis.periods.right.last}.</p>
          )}
          <p><strong>Règle :</strong> comparaison exacte après harmonisation de la casse et des espaces, sans deviner ni remplacer une valeur.</p>
        </div>
      )}
      {analysis.warnings.length > 0 && (
        <div className="warnings">
          {analysis.warnings.map((warning) => <p key={warning}>{warning}</p>)}
        </div>
      )}
      {(analysis.left_unmatched_samples.length > 0 || analysis.right_unmatched_samples.length > 0) && (
        <details>
          <summary>Voir quelques communes non retrouvées</summary>
          <div className="unmatched-grid">
            {[analysis.left_unmatched_samples, analysis.right_unmatched_samples].map((items, index) => (
              <div key={sources[index].id}>
                <strong>{sources[index].title}</strong>
                {items.length ? (
                  <ul>{items.map((item) => <li key={`${item.commune}-${item.année}`}>{item.commune}{item.année ? ` · ${item.année}` : ""}</li>)}</ul>
                ) : <p>Aucun exemple non apparié.</p>}
              </div>
            ))}
          </div>
        </details>
      )}
    </section>
  );
}

const aggregationLabels: Record<string, string> = {
  sum: "Somme",
  average: "Moyenne",
  minimum: "Minimum",
  maximum: "Maximum",
  count: "Nombre de valeurs",
};

function IndicatorBuilder({
  project,
  existing,
  onIndicatorChange,
}: {
  project: Project;
  existing: IndicatorResult | null;
  onIndicatorChange: (indicator: IndicatorResult) => void;
}) {
  const existingBySource = Object.fromEntries(
    (existing?.sources ?? []).map((source) => [source.dataset_id, source]),
  );
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(
    project.sources.map((source) => [
      source.id,
      existingBySource[source.id]?.value_column ?? bestMeasureColumn(source),
    ]),
  ));
  const [aggregations, setAggregations] = useState<Record<string, string>>(() => Object.fromEntries(
    project.sources.map((source) => [
      source.id,
      existingBySource[source.id]?.aggregation ?? "sum",
    ]),
  ));
  const [operation, setOperation] = useState<"ratio_percent" | "difference">(
    existing?.operation ?? "ratio_percent",
  );
  const [title, setTitle] = useState(existing?.title ?? "Comparaison des deux sources");
  const [result, setResult] = useState<IndicatorResult | null>(existing);
  const [calculating, setCalculating] = useState(false);
  const [error, setError] = useState("");
  const missingMeasure = project.sources.some((source) => !values[source.id]);

  async function calculate() {
    if (missingMeasure) {
      setError("Choisissez une colonne de valeur dans chaque source.");
      return;
    }
    setCalculating(true);
    setError("");
    try {
      const response = await fetch(
        `${apiUrl}/api/projects/${encodeURIComponent(project.id)}/indicator`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: title.trim() || "Comparaison des deux sources",
            operation,
            sources: project.sources.map((source) => ({
              dataset_id: source.id,
              value_column: values[source.id],
              aggregation: aggregations[source.id],
            })),
          }),
        },
      );
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "L’indicateur n’a pas pu être calculé.");
      setResult(body);
      onIndicatorChange(body);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "L’indicateur n’a pas pu être calculé.");
    } finally {
      setCalculating(false);
    }
  }

  return (
    <section className="indicator-builder" aria-labelledby="indicator-builder-title">
      <div className="indicator-heading">
        <div>
          <p className="eyebrow">Étape 4</p>
          <h3 id="indicator-builder-title">Construire un indicateur vérifiable</h3>
        </div>
        <p>Choisissez ce qui doit être agrégé dans chaque source, puis la formule qui les relie.</p>
      </div>

      <label className="indicator-title">
        Nom de l’indicateur
        <input value={title} maxLength={160} onChange={(event) => setTitle(event.target.value)} />
      </label>

      <div className="indicator-source-grid">
        {project.sources.map((source, index) => {
          const candidates = source.columns.filter((column) => isNumericMeasure(column, source));
          return (
            <fieldset className="indicator-source" key={source.id}>
              <legend>Source {index + 1} · {source.title}</legend>
              <label>
                Valeur à utiliser
                <select
                  value={values[source.id] ?? ""}
                  onChange={(event) => setValues((current) => ({ ...current, [source.id]: event.target.value }))}
                >
                  <option value="">Choisir une valeur numérique</option>
                  {candidates.map((column) => <option value={column.name} key={column.name}>{column.name}</option>)}
                </select>
              </label>
              <ColumnDetails column={source.columns.find((column) => column.name === values[source.id])} />
              <label>
                Calcul par commune{source.dimensions?.année ? " et année" : ""}
                <select
                  value={aggregations[source.id] ?? "sum"}
                  onChange={(event) => setAggregations((current) => ({ ...current, [source.id]: event.target.value }))}
                >
                  {Object.entries(aggregationLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
                </select>
              </label>
            </fieldset>
          );
        })}
      </div>

      <fieldset className="operation-choice">
        <legend>Comment relier les deux résultats ?</legend>
        <label>
          <input
            type="radio"
            name="operation"
            checked={operation === "ratio_percent"}
            onChange={() => setOperation("ratio_percent")}
          />
          <span><strong>Rapport en pourcentage</strong> Source 1 ÷ source 2 × 100</span>
        </label>
        <label>
          <input
            type="radio"
            name="operation"
            checked={operation === "difference"}
            onChange={() => setOperation("difference")}
          />
          <span><strong>Différence</strong> Source 1 − source 2</span>
        </label>
      </fieldset>

      {error && <p className="error" role="alert">{error}</p>}
      <button onClick={calculate} disabled={calculating || missingMeasure || title.trim().length < 2}>
        {calculating ? "Calcul de l’indicateur…" : "Calculer et afficher"}
      </button>
      {result && (
        <>
          <IndicatorView indicator={result} />
          <PublicationBuilder project={{ ...project, indicator: result }} />
        </>
      )}
    </section>
  );
}

function IndicatorView({ indicator }: { indicator: IndicatorResult }) {
  return (
    <section className="indicator-result" aria-labelledby="indicator-result-title">
      <div className="indicator-result-heading">
        <div>
          <p className="eyebrow">Indicateur calculé</p>
          <h3 id="indicator-result-title">{indicator.title}</h3>
        </div>
        <strong>{indicator.result_count.toLocaleString("fr-FR")} résultats</strong>
      </div>
      <div className="formula-box">
        <span>Formule appliquée à chaque {indicator.dimensions.join(" + ")}</span>
        <code>{indicator.formula}</code>
      </div>
      {indicator.warnings.length > 0 && (
        <div className="warnings">{indicator.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div>
      )}
      {indicator.rows.length ? (
        <>
          <IndicatorChart indicator={indicator} />
          <details className="indicator-table-details">
            <summary>Voir les valeurs du calcul</summary>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Commune</th><th>Année</th><th>Source 1</th><th>Source 2</th><th>Indicateur</th></tr></thead>
                <tbody>
                  {indicator.rows.slice(0, 100).map((row) => (
                    <tr key={`${row.commune}-${row.année}`}>
                      <td>{row.commune}</td>
                      <td>{row.année ?? "—"}</td>
                      <td>{formatNumber(row.source_1_value)}</td>
                      <td>{formatNumber(row.source_2_value)}</td>
                      <td>{formatIndicator(row.value, indicator.unit)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      ) : (
        <p className="indicator-empty">Aucun résultat calculable avec ces valeurs. Les exclusions ci-dessus expliquent pourquoi.</p>
      )}
    </section>
  );
}

function IndicatorChart({ indicator }: { indicator: IndicatorResult }) {
  const rows = indicator.rows.slice(0, 12);
  const chartWidth = 920;
  const labelWidth = 225;
  const plotWidth = 570;
  const rowHeight = 42;
  const values = rows.map((row) => row.value);
  const minimum = Math.min(0, ...values);
  const maximum = Math.max(0, ...values);
  const range = maximum - minimum || 1;
  const zeroX = labelWidth + ((0 - minimum) / range) * plotWidth;
  const chartHeight = rows.length * rowHeight + 38;

  return (
    <figure className="indicator-chart">
      <figcaption>Valeurs les plus éloignées de zéro — jusqu’à 12 communes</figcaption>
      <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} role="img" aria-labelledby="chart-title chart-description">
        <title id="chart-title">{indicator.title}</title>
        <desc id="chart-description">Graphique en barres de {rows.length} résultats, exprimés en {indicator.unit}.</desc>
        <line x1={zeroX} x2={zeroX} y1="4" y2={chartHeight - 24} className="zero-line" />
        {rows.map((row, index) => {
          const y = index * rowHeight + 8;
          const valueX = labelWidth + ((row.value - minimum) / range) * plotWidth;
          const x = Math.min(zeroX, valueX);
          const width = Math.max(2, Math.abs(valueX - zeroX));
          const positive = row.value >= 0;
          return (
            <g key={`${row.commune}-${row.année}`}>
              <text x="4" y={y + 12} className="chart-label">{truncateLabel(row.commune, 24)}{row.année ? ` · ${row.année}` : ""}</text>
              <rect x={x} y={y} width={width} height="18" rx="3" className={positive ? "bar-positive" : "bar-negative"} />
              <text
                x={positive ? x + width + 7 : x - 7}
                y={y + 12}
                textAnchor={positive ? "start" : "end"}
                className="chart-value"
              >
                {formatIndicator(row.value, indicator.unit)}
              </text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}

function PublicationBuilder({ project }: { project: Project }) {
  const router = useRouter();
  const indicator = project.indicator!;
  const join = project.join_analysis!;
  const [authorName, setAuthorName] = useState("");
  const [title, setTitle] = useState(indicator.title);
  const [summary, setSummary] = useState(
    `${indicator.title} a été calculé pour ${indicator.result_count.toLocaleString("fr-FR")} combinaison(s) ${indicator.dimensions.join(" + ")}.`,
  );
  const [interpretation, setInterpretation] = useState("");
  const [limitations, setLimitations] = useState(() => {
    const alerts = [...join.warnings, ...indicator.warnings];
    const coverage = `Les résultats portent uniquement sur les clés appariées : ${join.left_match_rate.toLocaleString("fr-FR")} % de la source 1 et ${join.right_match_rate.toLocaleString("fr-FR")} % de la source 2.`;
    return [coverage, ...alerts].join(" ");
  });
  const [versions, setVersions] = useState<VersionSummary[]>([]);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetch(`${apiUrl}/api/projects/${encodeURIComponent(project.id)}/versions`)
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail ?? "L’historique n’a pas pu être chargé.");
        if (active) setVersions(body);
      })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : "L’historique n’a pas pu être chargé.");
      });
    return () => { active = false; };
  }, [project.id]);

  async function publish(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPublishing(true);
    setError("");
    try {
      const response = await fetch(`${apiUrl}/api/projects/${encodeURIComponent(project.id)}/versions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          author_name: authorName,
          title,
          summary,
          interpretation,
          limitations,
        }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "La fiche n’a pas pu être publiée.");
      router.push(`/?publication=${encodeURIComponent(body.id)}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "La fiche n’a pas pu être publiée.");
      setPublishing(false);
    }
  }

  const canPublish = [authorName, title, summary, limitations].every((value) => value.trim().length >= 2);
  return (
    <section className="publication-builder" aria-labelledby="publication-builder-title">
      <div className="publication-builder-heading">
        <div>
          <p className="eyebrow">Étape 5</p>
          <h3 id="publication-builder-title">Publier une fiche citoyenne</h3>
        </div>
        <p>La publication fige les données, la méthode et le texte. Une correction créera une nouvelle version.</p>
      </div>
      <form onSubmit={publish}>
        <div className="publication-short-fields">
          <label>
            Nom ou pseudonyme
            <input value={authorName} maxLength={80} onChange={(event) => setAuthorName(event.target.value)} placeholder="Ex. Camille" />
          </label>
          <label>
            Titre de la fiche
            <input value={title} maxLength={160} onChange={(event) => setTitle(event.target.value)} />
          </label>
        </div>
        <label>
          Résumé factuel
          <textarea value={summary} maxLength={3000} rows={3} onChange={(event) => setSummary(event.target.value)} />
        </label>
        <label>
          Interprétation proposée <span>facultatif</span>
          <textarea
            value={interpretation}
            maxLength={5000}
            rows={4}
            onChange={(event) => setInterpretation(event.target.value)}
            placeholder="Distinguez ici votre lecture des faits calculés."
          />
        </label>
        <label>
          Précautions et limites
          <textarea value={limitations} maxLength={5000} rows={4} onChange={(event) => setLimitations(event.target.value)} />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button disabled={!canPublish || publishing}>{publishing ? "Publication…" : "Publier cette version"}</button>
      </form>
      {versions.length > 0 && (
        <div className="version-history compact-history">
          <strong>Versions déjà publiées</strong>
          {versions.map((version) => (
            <a href={`?publication=${encodeURIComponent(version.id)}`} key={version.id}>
              Version {version.version_number} · {version.title} · {formatDate(version.created_at)}
            </a>
          ))}
        </div>
      )}
    </section>
  );
}

function PublishedSheet({ publication }: { publication: PublishedVersion }) {
  return (
    <main className="published-page">
      <nav className="publication-nav" aria-label="Navigation de la fiche">
        <a href={`?project=${encodeURIComponent(publication.project_id)}`}>← Proposer une nouvelle version</a>
        <span>Version {publication.version_number} · immuable</span>
      </nav>
      <article className="published-sheet">
        <header className="published-header">
          <p className="eyebrow">Fiche citoyenne publiée</p>
          <h1>{publication.title}</h1>
          <p className="published-meta">
            Version {publication.version_number}, publiée par {publication.author_name} le {formatDate(publication.published_at)}
          </p>
          <p className="published-summary">{publication.summary}</p>
        </header>

        {publication.interpretation && (
          <section className="narrative-section">
            <p className="eyebrow">Interprétation proposée</p>
            <p>{publication.interpretation}</p>
          </section>
        )}

        <IndicatorView indicator={publication.indicator} />

        <section className="published-quality" aria-labelledby="published-quality-title">
          <p className="eyebrow">Qualité du croisement</p>
          <h2 id="published-quality-title">Ce qui correspond — et ce qui ne correspond pas</h2>
          <div className="match-metrics">
            <div><span>Clés appariées</span><strong>{publication.join_analysis.matched_keys.toLocaleString("fr-FR")}</strong></div>
            <div><span>Source 1 retrouvée</span><strong>{publication.join_analysis.left_match_rate.toLocaleString("fr-FR")} %</strong></div>
            <div><span>Source 2 retrouvée</span><strong>{publication.join_analysis.right_match_rate.toLocaleString("fr-FR")} %</strong></div>
          </div>
          {(publication.join_analysis.geography || publication.join_analysis.periods) && (
            <div className="scope-diagnostics">
              {publication.join_analysis.geography && (
                <p><strong>Périmètre géographique :</strong> {publication.join_analysis.geography.matched_communes.toLocaleString("fr-FR")} communes communes, sur {publication.join_analysis.geography.left_communes.toLocaleString("fr-FR")} dans la source 1 et {publication.join_analysis.geography.right_communes.toLocaleString("fr-FR")} dans la source 2.</p>
              )}
              {publication.join_analysis.periods && (
                <p><strong>Périodes :</strong> {publication.join_analysis.periods.left.first}–{publication.join_analysis.periods.left.last} dans la source 1 ; {publication.join_analysis.periods.right.first}–{publication.join_analysis.periods.right.last} dans la source 2.</p>
              )}
            </div>
          )}
          {publication.join_analysis.warnings.length > 0 && (
            <div className="warnings">{publication.join_analysis.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div>
          )}
        </section>

        <section className="published-sources" aria-labelledby="published-sources-title">
          <p className="eyebrow">Sources figées</p>
          <h2 id="published-sources-title">D’où viennent les données ?</h2>
          <div className="published-source-grid">
            {publication.sources.map((source) => (
              <article key={source.dataset_id}>
                <span>Source {source.position}</span>
                <h3>{source.title}</h3>
                <p>{source.publisher || source.catalog_source || "Producteur public"}</p>
                <dl>
                  <div><dt>Plateforme</dt><dd>{source.catalog_source || "Non précisée"}</dd></div>
                  <div><dt>Lignes</dt><dd>{source.row_count.toLocaleString("fr-FR")}</dd></div>
                  <div><dt>Commune</dt><dd>{source.dimensions.commune || "—"}</dd></div>
                  <div><dt>Année</dt><dd>{source.dimensions.année || "—"}</dd></div>
                </dl>
                {source.source_url && <a href={source.source_url} target="_blank" rel="noreferrer">Ouvrir la ressource d’origine ↗</a>}
                <code title="Empreinte SHA-256">SHA-256 · {source.sha256}</code>
              </article>
            ))}
          </div>
        </section>

        <section className="narrative-section limitations-section">
          <p className="eyebrow">Précautions d’interprétation</p>
          <p>{publication.limitations}</p>
        </section>

        <section className="reproducibility" aria-labelledby="reproducibility-title">
          <p className="eyebrow">Reproductibilité</p>
          <h2 id="reproducibility-title">Comment ce résultat a été obtenu</h2>
          <ol>
            <li>Les deux ressources ci-dessus ont été vérifiées avec leur empreinte SHA-256.</li>
            <li>{publication.reproducibility.key_normalization}</li>
            <li>La jointure utilise {publication.indicator.dimensions.join(" + ")} et conserve uniquement les clés appariées.</li>
            <li>La formule appliquée est : <code>{publication.indicator.formula}</code></li>
            <li>{publication.reproducibility.missing_data_policy}</li>
          </ol>
          <div className="snapshot-fingerprint">
            <span>Empreinte de cette version · {publication.integrity_verified ? "intégrité vérifiée" : "intégrité non vérifiée"}</span>
            <code>{publication.snapshot_sha256}</code>
          </div>
        </section>

        <VersionHistory versions={publication.versions} currentId={publication.id} />
        <PublicationComments publication={publication} />
      </article>
    </main>
  );
}

function VersionHistory({ versions, currentId }: { versions: VersionSummary[]; currentId: string }) {
  return (
    <section className="version-history" aria-labelledby="version-history-title">
      <p className="eyebrow">Historique</p>
      <h2 id="version-history-title">Versions publiées</h2>
      <div>
        {versions.map((version) => (
          <a className={version.id === currentId ? "current" : ""} href={`?publication=${encodeURIComponent(version.id)}`} key={version.id}>
            <strong>Version {version.version_number} · {version.title}</strong>
            <span>{version.author_name} · {formatDate(version.created_at)}</span>
            <code>{version.snapshot_sha256.slice(0, 16)}…</code>
          </a>
        ))}
      </div>
    </section>
  );
}

function PublicationComments({ publication }: { publication: PublishedVersion }) {
  const [comments, setComments] = useState(publication.comments);
  const [authorName, setAuthorName] = useState("");
  const [content, setContent] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSending(true);
    setError("");
    try {
      const response = await fetch(`${apiUrl}/api/publications/${encodeURIComponent(publication.id)}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ author_name: authorName, content }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Le commentaire n’a pas pu être ajouté.");
      setComments((current) => [...current, body]);
      setContent("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Le commentaire n’a pas pu être ajouté.");
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="publication-comments" aria-labelledby="comments-title">
      <p className="eyebrow">Discussion</p>
      <h2 id="comments-title">Contributions sur cette version</h2>
      {comments.length ? (
        <div className="comment-list">
          {comments.map((comment) => (
            <article key={comment.id}>
              <header><strong>{comment.author_name}</strong><time>{formatDateTime(comment.created_at)}</time></header>
              <p>{comment.content}</p>
            </article>
          ))}
        </div>
      ) : <p className="no-comments">Aucune contribution pour le moment.</p>}
      <form onSubmit={submit}>
        <label>Nom ou pseudonyme<input value={authorName} maxLength={80} onChange={(event) => setAuthorName(event.target.value)} /></label>
        <label>Commentaire<textarea value={content} maxLength={2000} rows={4} onChange={(event) => setContent(event.target.value)} /></label>
        {error && <p className="error" role="alert">{error}</p>}
        <button disabled={sending || authorName.trim().length < 2 || content.trim().length < 2}>
          {sending ? "Ajout…" : "Ajouter la contribution"}
        </button>
      </form>
    </section>
  );
}

function isNumericMeasure(column: Column, source: ProjectSource) {
  if (column.name === source.dimensions?.commune || column.name === source.dimensions?.année) return false;
  return /^(U?TINYINT|U?SMALLINT|U?INTEGER|U?BIGINT|HUGEINT|FLOAT|DOUBLE|DECIMAL|REAL)/.test(column.type);
}

function bestMeasureColumn(source: ProjectSource) {
  const candidates = source.columns.filter((column) => isNumericMeasure(column, source));
  const usefulTerms = ["valeur", "nombre", "total", "population", "voiture", "consommation", "montant", "effectif", "mesure"];
  return candidates.find((column) => usefulTerms.some((term) => column.name.toLocaleLowerCase("fr-FR").includes(term)))?.name
    ?? candidates.find((column) => !/(^|[ _.-])(id|code)([ _.-]|$)/i.test(column.name))?.name
    ?? candidates[0]?.name
    ?? "";
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 3 }).format(value);
}

function formatIndicator(value: number, unit: string) {
  return `${formatNumber(value)}${unit === "%" ? " %" : ""}`;
}

function truncateLabel(value: string, length: number) {
  return value.length > length ? `${value.slice(0, length - 1)}…` : value;
}

function translateType(value: string) {
  if (["BIGINT", "INTEGER", "SMALLINT", "DOUBLE", "DECIMAL"].some((type) => value.startsWith(type))) return "Nombre";
  if (value === "DATE" || value.startsWith("TIMESTAMP")) return "Date";
  if (value === "BOOLEAN") return "Oui / non";
  return "Texte";
}

function bestSuggestedColumn(columns: Column[], role: string) {
  const suggested = columns.filter((column) => column.suggested_roles?.includes(role));
  const exactNames = role === "commune" ? ["commune", "ville"] : ["année", "annee", "year"];
  return suggested.find((column) => exactNames.includes(column.name.toLocaleLowerCase("fr-FR")))?.name
    ?? suggested[0]?.name
    ?? "";
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value.slice(0, 10) : new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium" }).format(date);
}

function formatDateTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function formatSize(value: number) {
  if (value < 1024) return `${value} o`;
  if (value < 1024 * 1024) return `${Math.ceil(value / 1024)} Ko`;
  return `${(value / (1024 * 1024)).toFixed(1)} Mo`;
}
