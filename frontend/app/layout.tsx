import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "Explorateur de données publiques",
  description: "Trouver, comprendre et croiser des données publiques",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
