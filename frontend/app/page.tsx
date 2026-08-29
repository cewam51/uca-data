"use client";

import { FormEvent, useState } from "react";

type Column = { name: string; type: string };
type Dataset = {
  id: string;
  original_name: string;
  sha256: string;
  size_bytes: number;
  row_count: number;
  columns: Column[];
  preview: Record<string, unknown>[];
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setLoading(true);
    setError("");
    setDataset(null);
    const form = new FormData();
    form.append("file", file);

    try {
      const response = await fetch(`${apiUrl}/api/datasets`, { method: "POST", body: form });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Import impossible");
      setDataset(body);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Import impossible");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <header>
        <p className="eyebrow">Un commun accord · données ouvertes</p>
        <h1>Comprendre les données avant de décider.</h1>
        <p className="intro">Importez un CSV pour vérifier sa structure, son contenu et son empreinte numérique. Aucun calcul caché, aucun fichier modifié.</p>
      </header>

      <section className="upload-card">
        <form onSubmit={upload}>
          <label htmlFor="csv">Choisir un fichier CSV</label>
          <input id="csv" type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          <button disabled={!file || loading}>{loading ? "Analyse en cours…" : "Importer et analyser"}</button>
        </form>
        {error && <p className="error" role="alert">{error}</p>}
      </section>

      {dataset && <DatasetResult dataset={dataset} />}
    </main>
  );
}

function DatasetResult({ dataset }: { dataset: Dataset }) {
  return (
    <section className="result">
      <div className="summary">
        <div><span>Fichier</span><strong>{dataset.original_name}</strong></div>
        <div><span>Lignes</span><strong>{dataset.row_count.toLocaleString("fr-FR")}</strong></div>
        <div><span>Colonnes</span><strong>{dataset.columns.length}</strong></div>
        <div><span>Taille</span><strong>{Math.ceil(dataset.size_bytes / 1024)} Ko</strong></div>
      </div>
      <div className="hash"><span>SHA-256</span><code>{dataset.sha256}</code></div>

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
