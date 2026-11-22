import { useMemo, useState } from "react";

import { FilterContext } from "./filterContext";

export default function FilterProvider({ children }) {
  const [ticker, setTicker] = useState("BBCA");
  const [period, setPeriod] = useState("FY2025");
  const [basis, setBasis] = useState("consolidated");

  const value = useMemo(
    () => ({ ticker, period, basis, setTicker, setPeriod, setBasis }),
    [ticker, period, basis],
  );

  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>;
}
