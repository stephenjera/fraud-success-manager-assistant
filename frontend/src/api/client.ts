// src/api/client.ts
import axios from "axios";
import type {
  ExploreRequest,
  ExploreResponse,
  ExecuteRequest,
  DataGridResponse,
  BacktestRequest,
  BacktestResponse,
} from "../types/api";

const api = axios.create({
  baseURL: "/api", 
  headers: {
    "Content-Type": "application/json",
  },
});

export const apiService = {
  async exploreHypothesis(payload: ExploreRequest): Promise<ExploreResponse> {
    const response = await api.post<ExploreResponse>("/explore", payload);
    return response.data;
  },

  async executeSQL(payload: ExecuteRequest): Promise<DataGridResponse> {
    const response = await api.post<DataGridResponse>("/execute", payload);
    return response.data;
  },

  async runBacktest(payload: BacktestRequest): Promise<BacktestResponse> {
    const response = await api.post<BacktestResponse>("/backtest", payload);
    return response.data;
  },
};
