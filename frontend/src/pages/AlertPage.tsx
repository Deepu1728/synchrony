import { useParams } from "react-router-dom";

export function AlertPage() {
  const { id } = useParams();
  return (
    <section>
      <h1>Alert {id}</h1>
      <p className="muted">The alert detail view arrives in Step 5.</p>
    </section>
  );
}
