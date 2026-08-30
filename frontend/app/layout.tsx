import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "Explorateur de données publiques",
  description: "Trouver des données publiques et créer librement des graphiques vérifiables",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
