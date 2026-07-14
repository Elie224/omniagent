import { toast } from "@/components/Toast";

export function notifyCvGeneratedPdf() {
  toast({
    kind: "success",
    title: "CV genere",
    message: "CV genere en PDF avec succes.",
  });
}

export function notifyCvGeneratedTexOnly() {
  toast({
    kind: "warning",
    title: "Generation partielle",
    message: "CV genere en TEX. PDF indisponible pour l instant (pdflatex manquant).",
  });
}

export function notifyCvGenerateError(message?: string) {
  toast({
    kind: "error",
    title: "Generation impossible",
    message: message || "Generation du CV impossible.",
  });
}

export function notifyGeneratedCvDownloadStarted() {
  toast({
    kind: "success",
    title: "Telechargement lance",
    message: "Telechargement du CV genere demarre.",
  });
}

export function notifyGeneratedCvDownloadError(message?: string) {
  toast({
    kind: "error",
    title: "Telechargement impossible",
    message: message || "Telechargement du CV genere impossible.",
  });
}

export function notifyCvUploadInvalidFormat() {
  toast({
    kind: "error",
    title: "Upload impossible",
    message: "Le fichier doit etre un PDF (extension .pdf).",
  });
}

export function notifyCvUploadTooLarge(sizeLabel: string) {
  toast({
    kind: "error",
    title: "Upload impossible",
    message: `Fichier trop volumineux (${sizeLabel} > 5 MB).`,
  });
}

export function notifyCvUploaded() {
  toast({
    kind: "success",
    title: "CV televerse",
    message: "CV televerse avec succes.",
  });
}

export function notifyCvUploadError(message?: string) {
  toast({
    kind: "error",
    title: "Upload impossible",
    message: message || "Erreur lors du televersement",
  });
}

export function notifyCvDeleted() {
  toast({
    kind: "success",
    title: "CV supprime",
    message: "CV supprime.",
  });
}

export function notifyCvDeleteError(message?: string) {
  toast({
    kind: "error",
    title: "Suppression impossible",
    message: message || "Erreur lors de la suppression",
  });
}
