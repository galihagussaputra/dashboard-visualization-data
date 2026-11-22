import { createContext, useContext } from "react";

export const FilterContext = createContext(null);

export function useFilters() {
  const value = useContext(FilterContext);
  if (!value) throw new Error("useFilters must be used inside FilterProvider");
  return value;
}
