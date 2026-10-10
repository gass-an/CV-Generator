import { useContext } from "react";

import { AppContext } from "@/app/AppProvider";

export function useAppState() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useAppState doit être utilisé dans AppProvider.");
  }
  return context;
}
