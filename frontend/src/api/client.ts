import axios from "axios";
import type { QueryResponse } from "../types/api";

const BASE_URL = "http://localhost:8000";

export async function runQuery(question: string): Promise<QueryResponse> {
  // Axios handles the JSON stringifying and parsing automatically
  // It also automatically throws an error if the status is not 2xx
  const { data } = await axios.post<QueryResponse>(`${BASE_URL}/query`, {
    question,
  });
  return data;
}

export async function runInvestigation(
  session_id: string,
  question: string,
  mode: "new" | "refine" = "new"
): Promise<any> {
  const { data } = await axios.post<any>(`${BASE_URL}/api/investigation/run`, null, {
    params: { session_id, question, mode },
  });
  return data;
}

export async function getInvestigation(session_id: string): Promise<any> {
  const { data } = await axios.get<any>(`${BASE_URL}/api/investigation/${encodeURIComponent(session_id)}`);
  return data;
}
