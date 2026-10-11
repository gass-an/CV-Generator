import { ChevronDown, X } from "lucide-react";
import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

export function AvpCombobox({
  options,
  selectedValue,
  loading,
  error,
  onSelect,
}: {
  options: string[];
  selectedValue: string | null;
  loading: boolean;
  error: string | null;
  onSelect: (value: string | null) => void;
}) {
  const inputId = useId();
  const listboxId = `${inputId}-options`;
  const messageId = `${inputId}-message`;
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(selectedValue ?? "");
  const [isSearching, setIsSearching] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const listboxRef = useRef<HTMLUListElement>(null);
  const optionRefs = useRef<Array<HTMLLIElement | null>>([]);

  const filteredOptions = useMemo(() => {
    const normalizedQuery = isSearching
      ? query.trim().toLocaleLowerCase("fr-FR")
      : "";
    return Array.from(new Set(options))
      .sort((left, right) =>
        left.localeCompare(right, "fr-FR", { sensitivity: "base" }),
      )
      .filter((value) =>
        value.toLocaleLowerCase("fr-FR").startsWith(normalizedQuery),
      );
  }, [isSearching, options, query]);

  useEffect(() => {
    if (!open || activeIndex < 0) return;
    const listbox = listboxRef.current;
    const option = optionRefs.current[activeIndex];
    if (!listbox || !option) return;

    const optionTop = option.offsetTop;
    const optionBottom = optionTop + option.offsetHeight;
    if (optionTop < listbox.scrollTop) {
      listbox.scrollTop = optionTop;
    } else if (optionBottom > listbox.scrollTop + listbox.clientHeight) {
      listbox.scrollTop = optionBottom - listbox.clientHeight;
    }
  }, [activeIndex, open]);

  function select(value: string) {
    setQuery(value);
    setIsSearching(false);
    setOpen(false);
    setActiveIndex(-1);
    onSelect(value);
  }

  function clear() {
    setQuery("");
    setIsSearching(false);
    setOpen(true);
    setActiveIndex(-1);
    onSelect(null);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((current) =>
        filteredOptions.length === 0
          ? -1
          : current < filteredOptions.length - 1
            ? current + 1
            : 0,
      );
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((current) =>
        filteredOptions.length === 0
          ? -1
          : current > 0
            ? current - 1
            : filteredOptions.length - 1,
      );
    } else if (event.key === "Enter" && open && activeIndex >= 0) {
      event.preventDefault();
      select(filteredOptions[activeIndex]);
    } else if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      setActiveIndex(-1);
    }
  }

  const showList = open && !loading && !error;
  const activeOption =
    showList && activeIndex >= 0 ? `${listboxId}-${activeIndex}` : undefined;

  return (
    <div className="relative">
      <label htmlFor={inputId} className="text-sm font-semibold">
        Numéro AVP
      </label>
      <div className="relative mt-2">
        <input
          id={inputId}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={showList}
          aria-controls={listboxId}
          aria-activedescendant={activeOption}
          aria-describedby={loading || error ? messageId : undefined}
          autoComplete="off"
          value={query}
          placeholder="Tous les AVP"
          onFocus={() => {
            setOpen(true);
            if (selectedValue !== null && query === selectedValue) {
              setIsSearching(false);
            }
            setActiveIndex(-1);
          }}
          onClick={() => {
            setOpen(true);
            if (selectedValue !== null && query === selectedValue) {
              setIsSearching(false);
            }
          }}
          onBlur={() => setOpen(false)}
          onKeyDown={handleKeyDown}
          onChange={(event) => {
            setQuery(event.target.value);
            setIsSearching(true);
            setOpen(true);
            setActiveIndex(-1);
            if (selectedValue !== null) onSelect(null);
          }}
          className="border-field-border bg-field focus-visible:border-primary focus-visible:ring-primary/30 min-h-11 w-full rounded-lg border pr-11 pl-3 font-normal transition-shadow focus-visible:ring-4 focus-visible:outline-none"
        />
        {selectedValue ? (
          <button
            type="button"
            onMouseDown={(event) => event.preventDefault()}
            onClick={clear}
            className="text-muted-foreground hover:text-primary absolute top-1/2 right-1 flex size-9 -translate-y-1/2 items-center justify-center rounded-md"
            aria-label="Effacer le filtre AVP"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        ) : (
          <ChevronDown
            className="text-muted-foreground pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2"
            aria-hidden="true"
          />
        )}
      </div>

      {loading ? (
        <p id={messageId} className="text-muted-foreground mt-2 text-xs">
          Chargement des numéros AVP…
        </p>
      ) : error ? (
        <p id={messageId} className="text-accent mt-2 text-xs" role="alert">
          {error}
        </p>
      ) : null}

      {showList ? (
        <ul
          ref={listboxRef}
          id={listboxId}
          role="listbox"
          aria-label="Numéros AVP disponibles"
          className="border-field-border bg-card absolute z-30 mt-1 max-h-52 w-full overflow-y-auto rounded-lg border p-1 shadow-lg"
        >
          {filteredOptions.length === 0 ? (
            <li className="text-muted-foreground px-3 py-2 text-sm">
              Aucun AVP correspondant
            </li>
          ) : (
            filteredOptions.map((value, index) => (
              <li
                key={value}
                ref={(element) => {
                  optionRefs.current[index] = element;
                }}
                id={`${listboxId}-${index}`}
                role="option"
                aria-selected={value === selectedValue}
                onMouseDown={(event) => event.preventDefault()}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => select(value)}
                className={`cursor-pointer rounded-md px-3 py-2 text-sm ${
                  index === activeIndex
                    ? "bg-primary/10 text-primary"
                    : "hover:bg-muted"
                }`}
              >
                {value}
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}
