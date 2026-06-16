import React from 'react';

const SAMPLE_PETITION_META = {
  filename: 'ek-beyan-delil-degerlendirme-dilekcesi.docx',
  title: 'Ek Beyan ve Delil Değerlendirme Dilekçesi',
  court: 'ELBİSTAN SULH CEZA HÂKİMLİĞİ',
  date: 'Elbistan, 16.04.2026',
  signature: 'S**** K***',
};

const PETITION_INFO_ROWS = [
  {
    label: 'İtiraz Eden',
    value: 'S**** K***, T.C. Kimlik No: ***********, adres bilgisi maskelenmiştir.',
  },
  {
    label: 'Karşı Taraf',
    value: 'Elbistan Trafik Denetleme Büro Amirliği / Elbistan İlçe Emniyet Müdürlüğü',
  },
  {
    label: 'Dosya No',
    value: '2026/*** D.İş',
  },
  {
    label: 'Tutanak No',
    value: 'MB********',
  },
  {
    label: 'Konu',
    value:
      'İdarenin cevap yazısına karşı beyanlarımız, delil değerlendirmemiz ve itiraza konu idari yaptırımın iptali talebimizdir.',
  },
];

const EXPLANATION_BLOCKS = [
  {
    kind: 'paragraph',
    text:
      "İdarenin cevap yazısı, isnadı doğrulayan olay anı görüntüsünü değil; ceza tutanağı düzenlenirken başlatılmış, bağlamı kesilmiş ve öncesi-sonrası dosyaya sunulmamış bir yaka kamerası kesitini esas almaktadır. Dosyaya sunulan kayıtta, tarafımdan baskı altında 'evet drift çektim' şeklinde söz söyletildiği görülmekte; ancak bu kaydın öncesinde görevli polis memurlarının beni nezarethaneye götüreceklerini, itiraz edersem bu işin içinden çıkamayacağımı söyledikleri bölüm dosyaya hiç alınmamaktadır. Bu nedenle söz konusu ifade serbest iradeyle verilmiş bir ikrar olarak kabul edilemez; aksine bağlamından koparılmış, denetlenemez ve güvenilirliği ciddi biçimde tartışmalı bir kayıt parçasıdır.",
  },
  {
    kind: 'paragraph',
    text:
      "İdarenin cevabında özellikle dikkat çekici olan husus, olay anına ilişkin doğrudan görüntünün dosyaya sunulmamasıdır. Eğer gerçekten olay tarihinde Ergenekon Caddesi üzerinde 2918 sayılı Kanun'un 67/1-d maddesindeki anlamda 'bilerek ve isteyerek' drift fiili işlenmiş olsaydı, bu ağır isnadı doğrulayacak en elverişli delil olay anı görüntüsü olurdu. Oysa dosyaya getirilen kayıt, iddia edilen manevranın kendisini içermemekte; yalnızca sonradan başlayan ve baskı altında alınan sözleri içeren sınırlı bir kesiti göstermektedir.",
  },
  {
    kind: 'paragraph',
    text:
      "2918 sayılı Karayolları Trafik Kanunu'nun 67/1-d maddesi, herhangi bir zorunluluk olmaksızın karayollarında dönüş kuralları dışında 'bilerek ve isteyerek' aracın ani olarak yönünün değiştirilmesini veya kendi etrafında döndürülmesini yasaklamaktadır. Bu düzenlemede yaptırımın dayanağı, salt kayma değil; kast unsuru taşıyan bilinçli ve iradi bir manevradır. Karlı ve buzlu zeminde, düşük hızla seyir hâlindeki ticari aracın istem dışı tutunma kaybı yaşaması ile bilerek ve isteyerek drift yapılması aynı şey değildir.",
  },
  {
    kind: 'paragraph',
    text:
      "İdarenin ilk cevabında itiraz tarihini hatalı göstererek süre aşımı ileri sürmesi de dosya kapsamına aykırı açık maddi hata niteliğindedir. Tebliğden sonraki gün yapılan başvuruda 5326 sayılı Kabahatler Kanunu'nun 27/1 maddesinde öngörülen onbeş günlük süre açıkça korunmuştur. Süre yönünden ileri sürülen bu bariz hata, idarenin dosyayı gereken dikkat ve özenle incelemediğini göstermektedir.",
  },
  {
    kind: 'paragraph',
    text:
      "İdare ayrıca iki ayrı yazısında Yargıtay 7. Dairesine ait olduğu belirtilen bir karara dayanmış; ancak kararın tam künyesini, tarihini, mahkemesini ve uyuşmazlıkla bağını denetlenebilir şekilde ortaya koymamıştır. Tam künye verilmeden yapılan bu atıf, yargısal denetim ve tarafların savunma hakkı bakımından yeterli değildir.",
  },
  {
    kind: 'paragraph',
    text:
      'Yargıtay 7. Ceza Dairesinin 2021/20361 Esas, 2021/15838 Karar sayılı ve 25.11.2021 tarihli ilamında, trafik idari para cezası yargılamasında gerekli belgeler getirtilip inceleme ve araştırma yapılmadan karar verilemeyeceği vurgulanmıştır.',
  },
  {
    kind: 'quote',
    text:
      '...mahkemece, ilgili kamu kurumundan gerekli olan tüm belgeler getirtilip inceleme ve araştırma yapılmadan ... yazılı şekilde karar verilmesinde isabet görülmemiş...',
  },
  {
    kind: 'paragraph',
    text:
      'Bu karar, somut dosyada da olay anı görüntüsü bulunmaksızın ve yaka kamerası kaydının bağlamı çözümlenmeden, yalnızca tutanak anlatımı ile sonuca gidilemeyeceğini göstermektedir.',
  },
  {
    kind: 'paragraph',
    text:
      'Yargıtay 19. Ceza Dairesinin 2019/30283 Esas, 2021/3769 Karar sayılı ve 29.03.2021 tarihli ilamında, resmi tutanak mevcut olsa dahi başvurucunun belirli gün ve saatte başka bir olguya dayalı savunması bulunduğunda kamera kaydının araştırılması ve araç/olay mukayesesinin yapılması gerektiği kabul edilmiştir.',
  },
  {
    kind: 'quote',
    text:
      '...kamera kaydının bulunup bulunmadığı belirlenerek, kayıt var ise, kamera kayıtlarındaki araç ile başvuranın aracının mukayesesinin yaptırılması ... hiçbir şüpheye mahal vermeyecek şekilde ... belirlendikten sonra karar verilmesi gerektiği...',
  },
  {
    kind: 'paragraph',
    text:
      'Bu ilke uyarınca, somut olayda da olay anını gösteren tam kayıtlar, varsa KGYS/MOBESE görüntüleri ve DVD içeriğinin eksiksiz çözümü değerlendirilmeden ret kararı verilmesi hukuka aykırı olacaktır.',
  },
  {
    kind: 'paragraph',
    text:
      'Yargıtay 12. Ceza Dairesinin 2020/4770 Esas, 2023/694 Karar sayılı ve 07.03.2023 tarihli ilamında ise drift iddiasının kamera görüntüsüyle kesin ve her türlü şüpheden uzak biçimde ispatlanamadığı durumda aleyhe sonuca gidilemeyeceği açıkça ifade edilmiştir.',
  },
  {
    kind: 'quote',
    text:
      'Olaya ilişkin kamera görüntülerinin olay anını net göstermediği, sanığın direksiyon hakimiyetini kaybetme sebebinin anlaşılamadığı ... sanığın drift yapmak suretiyle direksiyon hakimiyetini kaybettiği kesin, her türlü şüpheden uzak olarak ispatlanamadığından...',
  },
  {
    kind: 'paragraph',
    text:
      "Her ne kadar bu karar ceza yargılamasına ilişkin ise de, 'drift' etiketi yapıştırılmasının tek başına yeterli olmadığı; olay anı net değilse ve kaydın içeriği şüphe doğuruyorsa sonucun aleyhe kurulamayacağı yönündeki yaklaşım, kabahat yargılamasında da maddi gerçeğin araştırılması bakımından yol göstericidir.",
  },
  {
    kind: 'paragraph',
    text:
      "Somut olayda yapılması gereken; sunulan DVD'nin tam çözümünün yaptırılması, kaydın başlangıç ve bitiş zamanlarının tespiti, olay anını içermeyen kesit ile idarenin anlatımı arasındaki boşluğun açıklattırılması, aynı tarih ve saat aralığına ilişkin tüm yaka kamerası, KGYS ve MOBESE kayıtlarının eksiksiz celbi, gerektiğinde trafik uzmanı bilirkişiden; karlı-buzlu zeminde, ticari araçla düşük hızla ilerlerken meydana gelen istem dışı kaymanın 67/1-d anlamında bilinçli drift manevrası sayılıp sayılamayacağı konusunda denetime elverişli rapor alınmasıdır.",
  },
];

const EVIDENCE_ITEMS = [
  'Trafik idari para cezası karar tutanağı',
  'Dosyaya sunulan DVD/yaka kamerası kaydının tamamı ve çözüm/deşifre tutanağı',
  'Olay anına ilişkin tüm yaka kamerası kayıtlarının ham ve kesintisiz halleri',
  'Olay saatine ilişkin KGYS/MOBESE ve sair kamera kayıtları',
  'Hava durumu, kar/buz durumu ve yol koşullarına ilişkin resmi veriler',
  'Gerekirse trafik uzmanı bilirkişi incelemesi',
  'Her türlü yasal delil',
];

const LEGAL_BASIS =
  '5326 sayılı Kabahatler Kanunu m.27 ve m.28, 2918 sayılı Karayolları Trafik Kanunu m.67/1-d, Anayasa m.36 ve ilgili mevzuat.';

const REQUEST_ITEMS = [
  'İdarenin cevap yazısında dayandığı, bağlamı kesilmiş ve olay anını içermeyen yaka kamerası kaydına üstün delil değeri tanınmamasına,',
  'Olay anını gösteren tüm yaka kamerası, KGYS, MOBESE ve sair kamera kayıtlarının eksiksiz olarak ilgili birimlerden celbine; bulunmadığı ileri sürülürse bunun nedenini ve kayıt akıbetini gösteren resmi tutanak ve yazıların dosyaya getirtilmesine,',
  'Dosyaya sunulan DVD kaydının başlangıç-bitiş zamanları ile bütünlüğünün tespiti için çözüm/deşifre incelemesi yaptırılmasına,',
  'Gerek görülmesi hâlinde, karlı ve buzlu zeminde meydana gelen istem dışı kaymanın 2918 sayılı Kanun m.67/1-d kapsamında bilinçli drift sayılıp sayılamayacağı hususunda trafik uzmanı bilirkişiden rapor alınmasına,',
  'İtirazımın kabulü ile idari yaptırım kararının ve buna bağlı sürücü belgesinin geri alınmasına ilişkin yaptırımın kaldırılmasına,',
  'Yargılama giderleri ile vekâlet ücretinin karşı tarafa yükletilmesine,',
];

function SectionTitle({ children }) {
  return (
    <h4 className="mt-8 border-b border-slate-200 pb-2 text-[11px] font-black uppercase tracking-[0.18em] text-slate-900 first:mt-0">
      {children}
    </h4>
  );
}

export function SamplePetitionDocument({ className = '', compact = false }) {
  return (
    <div className={`rounded-2xl border border-slate-200 bg-slate-100/70 p-2 shadow-2xl shadow-slate-950/10 ${className}`}>
      <div className="flex h-full flex-col overflow-hidden rounded-xl bg-white">
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3">
          <div className="min-w-0">
            <p className="truncate text-[11px] font-black uppercase tracking-[0.16em] text-slate-500">
              {SAMPLE_PETITION_META.filename}
            </p>
            <h3 className="truncate text-sm font-bold text-slate-950">{SAMPLE_PETITION_META.title}</h3>
          </div>
          <span className="shrink-0 rounded-full bg-slate-950 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-white">
            DOCX
          </span>
        </div>

        <article className="min-h-0 flex-1 overflow-y-auto px-5 py-6 text-slate-950 md:px-7">
          <div className={`mx-auto max-w-3xl ${compact ? 'text-[11px] leading-[1.65]' : 'text-[13px] leading-[1.8]'}`}>
            <h2 className="mb-6 text-center text-sm font-black uppercase tracking-wide text-slate-950 md:text-base">
              {SAMPLE_PETITION_META.court}
            </h2>

            <div className="space-y-3">
              {PETITION_INFO_ROWS.map((row) => (
                <div key={row.label} className="grid gap-1 border-b border-slate-100 pb-2 sm:grid-cols-[88px_1fr]">
                  <span className="font-bold text-slate-700">{row.label}</span>
                  <p className="text-slate-950">{row.value}</p>
                </div>
              ))}
            </div>

            <SectionTitle>Açıklamalar</SectionTitle>
            <div className="space-y-4 text-justify">
              {EXPLANATION_BLOCKS.map((block, index) => (
                block.kind === 'quote' ? (
                  <blockquote
                    key={index}
                    className="border-l-4 border-slate-300 bg-slate-50 px-4 py-3 text-slate-700"
                  >
                    {block.text}
                  </blockquote>
                ) : (
                  <p key={index}>{block.text}</p>
                )
              ))}
            </div>

            <SectionTitle>Deliller</SectionTitle>
            <ol className="list-decimal space-y-1.5 pl-5">
              {EVIDENCE_ITEMS.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ol>

            <SectionTitle>Hukuki Sebepler</SectionTitle>
            <p className="text-justify">{LEGAL_BASIS}</p>

            <SectionTitle>Netice ve Talep</SectionTitle>
            <p>Yukarıda açıklanan nedenlerle;</p>
            <ol className="mt-3 list-decimal space-y-2 pl-5 text-justify">
              {REQUEST_ITEMS.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ol>

            <div className="mt-8 text-right">
              <p>{SAMPLE_PETITION_META.date}</p>
              <p className="mt-5 font-bold">Arz ve talep ederim.</p>
              <p>{SAMPLE_PETITION_META.signature}</p>
            </div>
          </div>
        </article>
      </div>
    </div>
  );
}
