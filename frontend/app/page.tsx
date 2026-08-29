"use client";

import { FormEvent, useState } from "react";

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

type Column = { name: string; type: string };
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

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const examples = ["population par commune", "parc automobile", "consommation électrique"];

export default function Home() {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState<SearchResponse | null>(null);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [exploring, setExploring] = useState("");

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
        <button className="back" onClick={() => setDataset(null)}>← Revenir aux résultats</button>
        <DatasetResult dataset={dataset} />
      </main>
    );
  }

  return (
    <main>
      <header>
        <p className="eyebrow">Explorateur de données publiques</p>
        <h1>Trouver les faits derrière une question.</h1>
        <p className="intro">Écrivez simplement ce que vous cherchez. Le site s’occupe de trouver et d’ouvrir les fichiers techniques.</p>
      </header>

      <div className="journey" aria-label="Parcours de création">
        <span className="active"><b>1</b>Trouver des données</span>
        <span><b>2</b>Croiser deux sources</span>
        <span><b>3</b>Créer un graphique</span>
      </div>

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
      {search && <SearchResults search={search} exploring={exploring} onExplore={explore} />}
    </main>
  );
}

function SearchResults({
  search,
  exploring,
  onExplore,
}: {
  search: SearchResponse;
  exploring: string;
  onExplore: (result: SearchResult) => void;
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
          <ResultCard key={`${result.source}:${result.id}`} result={result} exploring={exploring} onExplore={onExplore} />
        ))}
      </div>
    </section>
  );
}

function ResultCard({
  result,
  exploring,
  onExplore,
}: {
  result: SearchResult;
  exploring: string;
  onExplore: (result: SearchResult) => void;
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
              : "Utiliser ces données"}
        </button>
        {result.url && <a href={result.url} target="_blank" rel="noreferrer">Voir la fiche source ↗</a>}
      </div>
    </article>
  );
}

function DatasetResult({ dataset }: { dataset: Dataset }) {
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

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value.slice(0, 10) : new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium" }).format(date);
}

function formatSize(value: number) {
  if (value < 1024) return `${value} o`;
  if (value < 1024 * 1024) return `${Math.ceil(value / 1024)} Ko`;
  return `${(value / (1024 * 1024)).toFixed(1)} Mo`;
}
