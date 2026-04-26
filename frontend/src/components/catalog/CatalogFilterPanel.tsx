import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { SlidersHorizontal, RotateCcw } from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Checkbox } from "@/components/ui/checkbox";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";

export type FilterState = {
  search: string;
  brands: string[];
  stores: string[];
  types: string[];
  priceRange: [number, number];
  inStock: boolean | null;
};

export const defaultFilters: FilterState = {
  search: "",
  brands: [],
  stores: [],
  types: [],
  priceRange: [0, 500],
  inStock: null,
};

interface Props {
  filters: FilterState;
  setFilters: React.Dispatch<React.SetStateAction<FilterState>>;
  availableBrands: string[];
  availableStores: string[];
  availableTypes: string[];
}

export default function CatalogFilterPanel({
  filters,
  setFilters,
  availableBrands,
  availableStores,
  availableTypes,
}: Props) {
  const activeCount =
    filters.brands.length +
    filters.stores.length +
    filters.types.length +
    (filters.priceRange[0] > 0 || filters.priceRange[1] < 500 ? 1 : 0) +
    (filters.inStock !== null ? 1 : 0);

  const toggleArrayItem = (key: keyof Pick<FilterState, "brands" | "stores" | "types">, item: string) => {
    setFilters((prev) => {
      const arr = prev[key];
      return {
        ...prev,
        [key]: arr.includes(item) ? arr.filter((x) => x !== item) : [...arr, item],
      };
    });
  };

  const resetFilters = () => {
    setFilters((prev) => ({ ...defaultFilters, search: prev.search }));
  };

  const sectionTrigger =
    "flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.14em] font-medium text-muted-foreground hover:text-foreground py-3 hover:no-underline";

  return (
    <Sheet>
      <SheetTrigger asChild>
        <button className="relative inline-flex items-center gap-1.5 h-9 px-3 rounded-md border border-border text-muted-foreground text-[12.5px] font-medium hover:text-foreground hover:border-muted-foreground transition-colors">
          <SlidersHorizontal size={13} strokeWidth={1.75} />
          Filters
          {activeCount > 0 && (
            <span className="ml-0.5 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded bg-foreground text-background font-mono text-[10px] font-semibold tabular-nums">
              {activeCount}
            </span>
          )}
        </button>
      </SheetTrigger>

      <SheetContent className="w-[340px] sm:w-[400px] border-l border-border bg-background p-0 flex flex-col">
        <SheetHeader className="px-6 py-5 border-b border-border flex flex-row items-center justify-between space-y-0">
          <div className="flex flex-col gap-0.5">
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              · Filters
            </span>
            <SheetTitle className="font-['Inter'] font-semibold text-foreground text-[16px] tracking-[-0.005em] m-0">
              Refine catalog
            </SheetTitle>
          </div>
          {activeCount > 0 && (
            <button
              onClick={resetFilters}
              className="inline-flex items-center gap-1 text-[11.5px] text-muted-foreground hover:text-foreground transition-colors"
            >
              <RotateCcw size={11} />
              Reset
            </button>
          )}
        </SheetHeader>

        <div className="flex-1 overflow-y-auto scrollbar-hide">
          <Accordion
            type="multiple"
            defaultValue={["price", "store", "brand", "type", "availability"]}
            className="w-full divide-y divide-border"
          >
            {/* Price Range */}
            <AccordionItem value="price" className="border-b-0 px-6">
              <AccordionTrigger className={sectionTrigger}>Price range</AccordionTrigger>
              <AccordionContent className="pb-4">
                <div className="pt-2">
                  <Slider
                    defaultValue={[0, 500]}
                    value={[filters.priceRange[0], filters.priceRange[1]]}
                    max={500}
                    step={5}
                    onValueChange={(val) => setFilters((p) => ({ ...p, priceRange: [val[0], val[1]] }))}
                    className="mb-4 cursor-pointer"
                  />
                  <div className="flex items-center justify-between font-mono text-[11px] tabular-nums">
                    <span className="px-2 py-1 rounded bg-surface border border-border text-foreground">
                      €{filters.priceRange[0]}
                    </span>
                    <span className="text-muted-foreground/50">→</span>
                    <span className="px-2 py-1 rounded bg-surface border border-border text-foreground">
                      €{filters.priceRange[1]}
                    </span>
                  </div>
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* Stores */}
            <AccordionItem value="store" className="border-b-0 px-6">
              <AccordionTrigger className={sectionTrigger}>
                <div className="flex items-center gap-2">
                  Stores
                  {filters.stores.length > 0 && (
                    <span className="font-mono text-[10px] tabular-nums text-foreground bg-surface-2 px-1.5 py-0.5 rounded border border-border">
                      {filters.stores.length}
                    </span>
                  )}
                </div>
              </AccordionTrigger>
              <AccordionContent className="pb-4">
                <div className="space-y-2.5 pt-1">
                  {availableStores.map((store) => {
                    const checked = filters.stores.includes(store);
                    return (
                      <label
                        key={store}
                        htmlFor={`store-${store}`}
                        className={cn(
                          "flex items-center gap-3 cursor-pointer group",
                          checked ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        <Checkbox
                          id={`store-${store}`}
                          checked={checked}
                          onCheckedChange={() => toggleArrayItem("stores", store)}
                          className="data-[state=checked]:bg-foreground data-[state=checked]:border-foreground data-[state=checked]:text-background"
                        />
                        <span className="text-[12.5px] flex-1 transition-colors">{store}</span>
                      </label>
                    );
                  })}
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* Brands */}
            <AccordionItem value="brand" className="border-b-0 px-6">
              <AccordionTrigger className={sectionTrigger}>
                <div className="flex items-center gap-2">
                  Brands
                  {filters.brands.length > 0 && (
                    <span className="font-mono text-[10px] tabular-nums text-foreground bg-surface-2 px-1.5 py-0.5 rounded border border-border">
                      {filters.brands.length}
                    </span>
                  )}
                </div>
              </AccordionTrigger>
              <AccordionContent className="pb-4">
                <div className="space-y-2.5 pt-1 max-h-[200px] overflow-y-auto pr-2 scrollbar-hide">
                  {availableBrands.map((brand) => {
                    const checked = filters.brands.includes(brand);
                    return (
                      <label
                        key={brand}
                        htmlFor={`brand-${brand}`}
                        className={cn(
                          "flex items-center gap-3 cursor-pointer",
                          checked ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        <Checkbox
                          id={`brand-${brand}`}
                          checked={checked}
                          onCheckedChange={() => toggleArrayItem("brands", brand)}
                          className="data-[state=checked]:bg-foreground data-[state=checked]:border-foreground data-[state=checked]:text-background"
                        />
                        <span className="text-[12.5px] flex-1 transition-colors">{brand}</span>
                      </label>
                    );
                  })}
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* Types */}
            <AccordionItem value="type" className="border-b-0 px-6">
              <AccordionTrigger className={sectionTrigger}>
                <div className="flex items-center gap-2">
                  Types
                  {filters.types.length > 0 && (
                    <span className="font-mono text-[10px] tabular-nums text-foreground bg-surface-2 px-1.5 py-0.5 rounded border border-border">
                      {filters.types.length}
                    </span>
                  )}
                </div>
              </AccordionTrigger>
              <AccordionContent className="pb-4">
                <div className="space-y-2.5 pt-1">
                  {availableTypes.map((type) => {
                    const checked = filters.types.includes(type);
                    return (
                      <label
                        key={type}
                        htmlFor={`type-${type}`}
                        className={cn(
                          "flex items-center gap-3 cursor-pointer",
                          checked ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        <Checkbox
                          id={`type-${type}`}
                          checked={checked}
                          onCheckedChange={() => toggleArrayItem("types", type)}
                          className="data-[state=checked]:bg-foreground data-[state=checked]:border-foreground data-[state=checked]:text-background"
                        />
                        <span className="text-[12.5px] flex-1 transition-colors">{type}</span>
                      </label>
                    );
                  })}
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* Availability */}
            <AccordionItem value="availability" className="border-b-0 px-6">
              <AccordionTrigger className={sectionTrigger}>Availability</AccordionTrigger>
              <AccordionContent className="pb-5">
                <div className="space-y-2.5 pt-1">
                  {[
                    { label: "Any", value: null },
                    { label: "In stock", value: true },
                    { label: "Out of stock", value: false },
                  ].map((option) => {
                    const checked = filters.inStock === option.value;
                    return (
                      <label
                        key={option.label}
                        htmlFor={`stock-${option.label}`}
                        className={cn(
                          "flex items-center gap-3 cursor-pointer",
                          checked ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        <Checkbox
                          id={`stock-${option.label}`}
                          checked={checked}
                          onCheckedChange={() => setFilters((p) => ({ ...p, inStock: option.value }))}
                          className="data-[state=checked]:bg-foreground data-[state=checked]:border-foreground data-[state=checked]:text-background"
                        />
                        <span className="text-[12.5px] flex-1 transition-colors">{option.label}</span>
                      </label>
                    );
                  })}
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>
      </SheetContent>
    </Sheet>
  );
}
