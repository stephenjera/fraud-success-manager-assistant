import axios from "axios";
import type{
  ExploreRequest,
  ExploreResponse,
  ExecuteRequest,
  DataGridResponse,
  RuleEvaluationRequest,
  RuleEvaluationResponse,
} from "../types/api";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const api = {
  explore: async (data: ExploreRequest): Promise<ExploreResponse> => {
    const res = await axios.post<ExploreResponse>(
      `${API_URL}/api/explore`,
      data,
    );
    return res.data;
  },

  execute: async (data: ExecuteRequest): Promise<DataGridResponse> => {
    const res = await axios.post<DataGridResponse>(
      `${API_URL}/api/execute`,
      data,
    );
    return res.data;
  },

  evaluateRule: async (
    data: RuleEvaluationRequest,
  ): Promise<RuleEvaluationResponse> => {
    const res = await axios.post<RuleEvaluationResponse>(
      `${API_URL}/api/rules/evaluate`,
      data,
    );
    return res.data;
  },
};
