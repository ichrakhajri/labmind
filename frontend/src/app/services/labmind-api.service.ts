import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, throwError, delay } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class LabmindApiService {
  private http = inject(HttpClient);

  // Branché par défaut sur le backend FastAPI réel (lancer Angular sur --port 3000)
  // Passer useMock à true uniquement pour tester sans le serveur Python
  readonly useMock = false;
  readonly apiUrl = 'http://127.0.0.1:8000/v1';

  private mockPollCount = 0;
  private mockAnsweredUnit: string | null = null;
  private mockDeleted = false;
  private mockFilename = 'bilan.pdf';

  private readonly mockDisclaimer =
    'Outil pédagogique : ce bilan ne remplace pas une consultation médicale et ne constitue ni un diagnostic ni une prescription.';

  // GET /v1/health
  checkHealth(): Observable<any> {
    if (!this.useMock) {
      return this.http.get(`${this.apiUrl}/health`);
    }
    return of({ status: 'ok' });
  }

  // POST /v1/tasks
  createTask(file: File): Observable<any> {
    if (!this.useMock) {
      const formData = new FormData();
      formData.append('file', file);
      return this.http.post(`${this.apiUrl}/tasks`, formData);
    }

    const ext = file.name.split('.').pop()?.toLowerCase() || '';
    if (!['pdf', 'png', 'jpg', 'jpeg'].includes(ext)) {
      return throwError(() => ({
        status: 415,
        error: {
          error: {
            code: 'unsupported_format',
            message: 'Format non supporté (pdf, png, jpg, jpeg).'
          }
        }
      })).pipe(delay(300));
    }

    if (file.size > 10 * 1024 * 1024) {
      return throwError(() => ({
        status: 413,
        error: {
          error: {
            code: 'file_too_large',
            message: 'Le fichier dépasse la taille maximale autorisée (10 Mo).'
          }
        }
      })).pipe(delay(300));
    }

    this.mockPollCount = 0;
    this.mockAnsweredUnit = null;
    this.mockDeleted = false;
    this.mockFilename = file.name;

    return of({
      task_id: '3f2b8c1e-6a52-4d7e-9a0c-1b2d3e4f5a6b',
      status: 'received',
      document: { filename: this.mockFilename, extraction_method: null },
      detected_categories: [],
      parameters: [],
      pending_question: null,
      report_id: null,
      explanations: null,
      sources: [],
      disclaimer: this.mockDisclaimer,
      errors: []
    }).pipe(delay(400));
  }

  // GET /v1/tasks/{task_id}
  getTask(taskId: string): Observable<any> {
    if (!this.useMock) {
      return this.http.get(`${this.apiUrl}/tasks/${taskId}`);
    }

    if (this.mockDeleted) {
      return throwError(() => ({
        status: 404,
        error: {
          error: {
            code: 'task_not_found',
            message: 'Tâche introuvable ou supprimée.'
          }
        }
      }));
    }

    this.mockPollCount++;

    if (this.mockPollCount === 1) {
      return of({
        task_id: taskId,
        status: 'processing',
        document: { filename: this.mockFilename, extraction_method: null },
        detected_categories: [],
        parameters: [],
        pending_question: null,
        report_id: null,
        explanations: null,
        sources: [],
        disclaimer: this.mockDisclaimer,
        errors: []
      });
    }

    if (this.mockPollCount === 2 && this.mockAnsweredUnit === null) {
      return of({
        task_id: taskId,
        status: 'waiting_for_user',
        document: { filename: this.mockFilename, extraction_method: 'pdf_text' },
        detected_categories: ['NFS'],
        parameters: [
          {
            code: 'HCT',
            name_printed: 'Hématocrite',
            value: 46.0,
            unit: null,
            reference: { min: 37.0, max: 47.0, origin: 'document_laboratoire' },
            status: 'not_analyzed',
            reason: 'unité absente du document',
            confidence: 0.88,
            evidence: { raw_text: 'Hématocrite 46,0 37 - 47', page: 1 }
          }
        ],
        pending_question: {
          question_id: 'q-001',
          field: 'unit',
          code: 'HCT',
          message:
            "L'unité de ce paramètre est absente du document. Quelle unité figure sur votre compte rendu ?",
          options: ['%', 'autre', 'je ne sais pas']
        },
        report_id: null,
        explanations: null,
        sources: [],
        disclaimer: this.mockDisclaimer,
        errors: []
      });
    }

    const hctAnswered = this.mockAnsweredUnit !== 'je ne sais pas';
    return of({
      task_id: taskId,
      status: 'done',
      document: { filename: this.mockFilename, extraction_method: 'pdf_text' },
      detected_categories: ['NFS', 'Bilan glycémique'],
      parameters: [
        {
          code: 'HGB',
          name_printed: 'Hémoglobine',
          value: 10.5,
          unit: 'g/dL',
          reference: { min: 12.0, max: 16.0, origin: 'document_laboratoire' },
          status: 'below_reference',
          reason: null,
          confidence: 0.96,
          evidence: { raw_text: 'Hémoglobine 10,5 g/dL 12,0 - 16,0', page: 1 }
        },
        hctAnswered
          ? {
              code: 'HCT',
              name_printed: 'Hématocrite',
              value: 46.0,
              unit: this.mockAnsweredUnit || '%',
              reference: { min: 37.0, max: 47.0, origin: 'document_laboratoire' },
              status: 'within_reference',
              reason: null,
              confidence: 0.95,
              evidence: { raw_text: 'Hématocrite 46,0 37 - 47', page: 1 }
            }
          : {
              code: 'HCT',
              name_printed: 'Hématocrite',
              value: 46.0,
              unit: null,
              reference: { min: 37.0, max: 47.0, origin: 'document_laboratoire' },
              status: 'not_analyzed',
              reason: 'unité non confirmée par l’utilisateur',
              confidence: 0.88,
              evidence: { raw_text: 'Hématocrite 46,0 37 - 47', page: 1 }
            }
      ],
      pending_question: null,
      report_id: 'r-3f2b8c1e',
      explanations: {
        summary: 'Explications pédagogiques produites exclusivement à partir des sources documentaires vérifiées.',
        parameter_explanations: [
          {
            code: 'HGB',
            status: 'grounded',
            text: "L'hémoglobine est une protéine présente dans les globules rouges qui transporte l'oxygène. Votre valeur est située en dessous de la fourchette indiquée par votre laboratoire.",
            source_ids: ['ameli-prise-sang-2026']
          },
          {
            code: 'HCT',
            status: hctAnswered ? 'grounded' : 'not_analyzed',
            text: hctAnswered
              ? "L'hématocrite correspond au volume occupé par les globules rouges dans le sang. Votre valeur est située dans la fourchette du laboratoire."
              : "Ce paramètre n'a pas été analysé car son unité n'a pas été confirmée.",
            source_ids: hctAnswered ? ['ameli-prise-sang-2026'] : []
          }
        ]
      },
      sources: [
        {
          source_id: 'ameli-prise-sang-2026',
          title: "Comment lire les résultats d'une prise de sang ?",
          organisme: 'Assurance Maladie (ameli.fr)',
          url: 'https://www.ameli.fr/assure/sante/examen/analyse/lire-resultats-prise-sang',
          date: '2026-01-08'
        }
      ],
      disclaimer: this.mockDisclaimer,
      errors: []
    });
  }

  // POST /v1/tasks/{task_id}/answer
  submitAnswer(taskId: string, questionId: string, answer: string): Observable<any> {
    if (!this.useMock) {
      return this.http.post(`${this.apiUrl}/tasks/${taskId}/answer`, {
        question_id: questionId,
        answer
      });
    }

    if (!answer.trim()) {
      return throwError(() => ({
        status: 422,
        error: {
          error: {
            code: 'invalid_answer',
            message: 'Veuillez choisir une option ou saisir une valeur.'
          }
        }
      }));
    }

    this.mockAnsweredUnit = answer.trim();
    return this.getTask(taskId).pipe(delay(300));
  }

  // GET /v1/tasks/{task_id}/report.pdf
  getReportPdfUrl(taskId: string): string {
    return `${this.apiUrl}/tasks/${taskId}/report.pdf`;
  }

  // DELETE /v1/tasks/{task_id}
  deleteTask(taskId: string): Observable<void> {
    if (!this.useMock) {
      return this.http.delete<void>(`${this.apiUrl}/tasks/${taskId}`);
    }
    this.mockDeleted = true;
    return of(void 0).pipe(delay(300));
  }

  // Extraire { code, message } selon {"error": {"code", "message"}}
  formatError(err: any): { code: string; message: string } {
    const apiErr = err?.error?.error;
    if (apiErr?.code && apiErr?.message) {
      return { code: apiErr.code, message: apiErr.message };
    }
    if (err?.status === 0) {
      return {
        code: 'connection_refused',
        message:
          "Impossible de joindre le serveur backend sur http://127.0.0.1:8000. Vérifiez qu'uvicorn est démarré et qu'Angular tourne sur le port 3000."
      };
    }
    return {
      code: 'internal_error',
      message: 'Une erreur technique est survenue lors de la communication avec le serveur.'
    };
  }
}
