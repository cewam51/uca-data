"use client";

import { FormEvent, useEffect, useState } from "react";

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
  warnings: string[];
};

type Project = {
  id: string;
  title: string;
  created_at: string;
  sources: ProjectSource[];
  join_analysis?: JoinAnalysis | null;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const examples = ["population par commune", "parc automobile", "consommation électrique"];

export default function Home() {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState<SearchResponse | null>(null);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [exploring, setExploring] = useState("");

  useEffect(() => {
    const projectId = new URLSearchParams(window.location.search).get("project");
    if (!projectId) return;
    let active = true;
    fetch(`${apiUrl}/api/projects/${encodeURIComponent(projectId)}`)
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail ?? "Le projet n’a pas pu être retrouvé.");
        if (active) setProject(body);
      })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : "Le projet n’a pas pu être retrouvé.");
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
      <span><b>4</b>Créer un indicateur</span>
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
      {join && <JoinQuality analysis={join} sources={qualified.sources} />}
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

function formatSize(value: number) {
  if (value < 1024) return `${value} o`;
  if (value < 1024 * 1024) return `${Math.ceil(value / 1024)} Ko`;
  return `${(value / (1024 * 1024)).toFixed(1)} Mo`;
}
