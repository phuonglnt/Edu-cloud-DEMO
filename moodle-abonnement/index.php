<?php
// Page d'abonnement de l'utilisateur connecté à Moodle.
// Tout passe par stats-api (tier, quota, paiement simulé) : le navigateur
// ne parle jamais directement à stats-api, et l'utilisateur ne peut payer
// que pour son propre compte.

require(__DIR__ . '/../../config.php');
require_once($CFG->libdir . '/filelib.php');

require_login();
if (isguestuser()) {
    throw new moodle_exception('noguest');
}

$PAGE->set_url(new moodle_url('/local/abonnement/index.php'));
$PAGE->set_context(context_system::instance());
$PAGE->set_pagelayout('standard');
$PAGE->set_title('Abonnement');
$PAGE->set_heading('Abonnement');

$api = rtrim(getenv('STATS_API_URL') ?: 'http://stats-api:8000', '/');
// L'e-mail relie le compte Moodle au compte de l'assistant IA (Open WebUI)
$userid = core_text::strtolower($USER->email);
$libelles = ['GOLD' => 'GOLD (50 questions)', 'PLATINUM' => 'PLATINUM (illimité)'];

// Appel JSON à stats-api ; retourne [code HTTP, corps décodé].
function local_abonnement_appel(string $url, ?array $donnees = null): array {
    // ignoresecurity : stats-api est un service interne du réseau Docker
    $curl = new curl(['ignoresecurity' => true]);
    $options = ['CURLOPT_TIMEOUT' => 60];
    if ($donnees === null) {
        $reponse = $curl->get($url, null, $options);
    } else {
        $curl->setHeader(['Content-Type: application/json']);
        $reponse = $curl->post($url, json_encode($donnees), $options);
    }
    $corps = json_decode((string) $reponse, true);
    return [(int) ($curl->get_info()['http_code'] ?? 0), is_array($corps) ? $corps : []];
}

// Traitement du paiement.
$message = null;
$tier = optional_param('tier', '', PARAM_ALPHA);
if ($tier !== '' && confirm_sesskey()) {
    $carte = required_param('carte', PARAM_TEXT);
    [$code, $corps] = local_abonnement_appel("$api/api/upgrade",
        ['user_id' => $userid, 'tier' => $tier, 'carte' => $carte]);
    if ($code === 200) {
        $message = ['Paiement accepté : vous êtes maintenant au niveau ' . $corps['tier'] . '.', 'success'];
    } else if (isset($corps['detail']) && is_string($corps['detail'])) {
        $message = [$corps['detail'], 'error'];
    } else {
        $message = ['Le paiement a échoué. Réessayez dans quelques instants.', 'error'];
    }
}

[$code, $abonnement] = local_abonnement_appel("$api/api/subscription/" . rawurlencode($userid));

echo $OUTPUT->header();

if ($message) {
    echo $OUTPUT->notification($message[0], $message[1]);
}

if ($code !== 200) {
    echo $OUTPUT->notification('Impossible de charger votre abonnement pour le moment.', 'error');
    echo $OUTPUT->footer();
    exit;
}

$quota = $abonnement['limite'] === null
    ? $abonnement['questions_utilisees'] . ' (illimité)'
    : $abonnement['questions_utilisees'] . ' / ' . $abonnement['limite'];

echo html_writer::tag('p', 'Niveau actuel : ' . html_writer::tag('strong', s($abonnement['tier'])));
echo html_writer::tag('p', 'Questions utilisées : ' . html_writer::tag('strong', s($quota)));

$ordre = ['FREE', 'GOLD', 'PLATINUM'];
$superieurs = array_slice($ordre, array_search($abonnement['tier'], $ordre) + 1);

if (!$superieurs) {
    echo html_writer::tag('p', 'Vous êtes déjà au niveau le plus élevé.');
} else {
    $options = array_intersect_key($libelles, array_flip($superieurs));
    echo html_writer::start_tag('form', ['method' => 'post', 'action' => $PAGE->url, 'class' => 'mt-4', 'style' => 'max-width: 420px']);
    echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'sesskey', 'value' => sesskey()]);
    echo html_writer::start_div('mb-3');
    echo html_writer::label('Passer au niveau', 'abonnement-tier');
    echo html_writer::select($options, 'tier', '', false, ['id' => 'abonnement-tier', 'class' => 'form-control']);
    echo html_writer::end_div();
    echo html_writer::start_div('mb-3');
    echo html_writer::label('Numéro de carte', 'abonnement-carte');
    echo html_writer::empty_tag('input', ['type' => 'text', 'name' => 'carte', 'id' => 'abonnement-carte',
        'class' => 'form-control', 'inputmode' => 'numeric', 'autocomplete' => 'off',
        'placeholder' => '4242 4242 4242 4242', 'required' => 'required']);
    echo html_writer::end_div();
    echo html_writer::tag('button', 'Payer', ['type' => 'submit', 'class' => 'btn btn-primary']);
    echo html_writer::end_tag('form');
    echo html_writer::tag('p', 'Paiement simulé : 4242 4242 4242 4242 est acceptée, 4000 0000 0000 0002 est refusée.',
        ['class' => 'text-muted small mt-3']);
}

echo $OUTPUT->footer();
