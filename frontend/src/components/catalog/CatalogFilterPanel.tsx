import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { SlidersHorizontal, RotateCcw } from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Checkbox } from "@/components/ui/checkbox";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";

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

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline" className="relative h-9 gap-2 text-[13px] bg-surface-2 border-border hover:bg-surface-2/80 hover:text-primary transition-all shadow-sm">
          <SlidersHorizontal size={14} />
          Filters
          {activeCount > 0 && (
            <Badge variant="secondary" className="ml-1 px-1.5 h-5 rounded-full bg-primary text-primary-foreground text-[10px] font-bold border-0 flex items-center justify-center min-w-[20px]">
              {activeCount}
            </Badge>
          )}
        </Button>
      </SheetTrigger>
      
      <SheetContent className="w-[340px] sm:w-[400px] border-l border-border bg-surface/95 backdrop-blur-xl p-0 flex flex-col">
        <SheetHeader className="p-6 border-b border-border bg-background/50 flex flex-row items-center justify-between space-y-0">
          <SheetTitle className="text-lg font-display tracking-tight text-foreground m-0">Filters</SheetTitle>
          {activeCount > 0 && (
            <Button variant="ghost" size="sm" onClick={resetFilters} className="h-8 gap-1.5 text-muted-foreground hover:text-foreground text-xs hover:bg-surface-2 m-0 relative -top-1">
              <RotateCcw size={12} />
              Reset
            </Button>
          )}
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4 scrollbar-hide">
          <Accordion type="multiple" defaultValue={["price", "store", "brand", "type", "availability"]} className="w-full space-y-4">
            
            {/* Price Range */}
            <AccordionItem value="price" className="border-border bg-surface-2/30 rounded-xl px-4">
              <AccordionTrigger className="text-[14px] font-semibold hover:no-underline py-4">Price Range</AccordionTrigger>
              <AccordionContent className="pb-4">
                <div className="pt-2">
                  <Slider
                    defaultValue={[0, 500]}
                    value={[filters.priceRange[0], filters.priceRange[1]]}
                    max={500}
                    step={5}
                    onValueChange={(val) => setFilters((p) => ({ ...p, priceRange: [val[0], val[1]] }))}
                    className="mb-6 cursor-pointer"
                  />
                  <div className="flex items-center justify-between text-[13px] font-display font-medium tabular-nums tracking-tight">
                    <span className="bg-surface-2 px-2 py-1 rounded-md border border-border">€{filters.priceRange[0]}</span>
                    <span className="text-muted-foreground">-</span>
                    <span className="bg-surface-2 px-2 py-1 rounded-md border border-border">€{filters.priceRange[1]}</span>
                  </div>
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* Stores */}
            <AccordionItem value="store" className="border-border bg-surface-2/30 rounded-xl px-4">
              <AccordionTrigger className="text-[14px] font-semibold hover:no-underline py-4">
                <div className="flex items-center">
                  Stores
                  {filters.stores.length > 0 && <span className="ml-2 text-[11px] text-primary bg-primary/10 px-1.5 py-0.5 rounded-full">{filters.stores.length}</span>}
                </div>
              </AccordionTrigger>
              <AccordionContent className="pb-4">
                <div className="space-y-3 pt-1">
                  {availableStores.map((store) => (
                    <div key={store} className="flex items-center space-x-3 group">
                      <Checkbox 
                        id={`store-${store}`} 
                        checked={filters.stores.includes(store)}
                        onCheckedChange={() => toggleArrayItem("stores", store)}
                        className="data-[state=checked]:bg-primary data-[state=checked]:border-primary"
                      />
                      <label htmlFor={`store-${store}`} className="text-[13px] font-medium leading-none cursor-pointer group-hover:text-primary transition-colors flex-1">
                        {store}
                      </label>
                    </div>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* Brands */}
            <AccordionItem value="brand" className="border-border bg-surface-2/30 rounded-xl px-4">
              <AccordionTrigger className="text-[14px] font-semibold hover:no-underline py-4">
                <div className="flex items-center">
                  Brands
                  {filters.brands.length > 0 && <span className="ml-2 text-[11px] text-primary bg-primary/10 px-1.5 py-0.5 rounded-full">{filters.brands.length}</span>}
                </div>
              </AccordionTrigger>
              <AccordionContent className="pb-4">
                <div className="space-y-3 pt-1 max-h-[200px] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-surface-2 scrollbar-track-transparent">
                  {availableBrands.map((brand) => (
                    <div key={brand} className="flex items-center space-x-3 group">
                      <Checkbox 
                        id={`brand-${brand}`} 
                        checked={filters.brands.includes(brand)}
                        onCheckedChange={() => toggleArrayItem("brands", brand)}
                        className="data-[state=checked]:bg-primary data-[state=checked]:border-primary"
                      />
                      <label htmlFor={`brand-${brand}`} className="text-[13px] font-medium leading-none cursor-pointer group-hover:text-primary transition-colors flex-1">
                        {brand}
                      </label>
                    </div>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* Types */}
            <AccordionItem value="type" className="border-border bg-surface-2/30 rounded-xl px-4">
              <AccordionTrigger className="text-[14px] font-semibold hover:no-underline py-4">
                <div className="flex items-center">
                  Types
                  {filters.types.length > 0 && <span className="ml-2 text-[11px] text-primary bg-primary/10 px-1.5 py-0.5 rounded-full">{filters.types.length}</span>}
                </div>
              </AccordionTrigger>
              <AccordionContent className="pb-4">
                <div className="space-y-3 pt-1 border-t border-border/50 pt-3">
                  {availableTypes.map((type) => (
                    <div key={type} className="flex items-center space-x-3 group">
                      <Checkbox 
                        id={`type-${type}`} 
                        checked={filters.types.includes(type)}
                        onCheckedChange={() => toggleArrayItem("types", type)}
                        className="data-[state=checked]:bg-primary data-[state=checked]:border-primary"
                      />
                      <label htmlFor={`type-${type}`} className="text-[13px] font-medium leading-none cursor-pointer group-hover:text-primary transition-colors flex-1">
                        {type}
                      </label>
                    </div>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* Availability */}
            <AccordionItem value="availability" className="border-border bg-surface-2/30 rounded-xl px-4">
              <AccordionTrigger className="text-[14px] font-semibold hover:no-underline py-4">Availability</AccordionTrigger>
              <AccordionContent className="pb-4">
                <div className="space-y-3 pt-1">
                  {[
                    { label: "Any", value: null },
                    { label: "In Stock", value: true },
                    { label: "Out of Stock", value: false },
                  ].map((option) => (
                    <div key={option.label} className="flex items-center space-x-3 group">
                      <Checkbox 
                        id={`stock-${option.label}`}
                        checked={filters.inStock === option.value}
                        onCheckedChange={() => setFilters((p) => ({ ...p, inStock: option.value }))}
                        className="rounded-full data-[state=checked]:bg-primary data-[state=checked]:border-primary"
                      />
                      <label htmlFor={`stock-${option.label}`} className="text-[13px] font-medium leading-none cursor-pointer group-hover:text-primary transition-colors flex-1">
                        {option.label}
                      </label>
                    </div>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>

          </Accordion>
        </div>
      </SheetContent>
    </Sheet>
  );
}
