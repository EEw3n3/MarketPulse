import { Toaster as Sonner, toast } from "sonner";

type ToasterProps = React.ComponentProps<typeof Sonner>;

// Light only, like the rest of the redesign.
const Toaster = ({ ...props }: ToasterProps) => (
  <Sonner
    theme="light"
    position="bottom-center"
    className="toaster group"
    toastOptions={{
      classNames: {
        toast: "group toast mp-toast",
        description: "group-[.toast]:text-muted-foreground",
        actionButton: "mp-toast-act",
        cancelButton: "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
      },
    }}
    {...props}
  />
);

export { Toaster, toast };
